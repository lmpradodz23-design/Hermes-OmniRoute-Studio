"""Provider Catalog / Free-First Routing  ->  OmniRoute REAL bridge (§1-43 wiring).

This is the minimal adapter that connects the new selection layer to the EXISTING
OmniRoute execution path. It creates NO new transport and NO parallel router and
does NOT duplicate ProviderProfile. Flow:

    ProviderCatalog -> provider_routing.select_provider (free-first / LOCAL_ONLY /
    cost-guard) -> ProviderOmniRouteBridge -> providers.get_provider_profile() ->
    agent/transports/chat_completions.py (existing) -> real provider.

The bridge:
  - takes the normalized routing decision;
  - resolves the REAL existing ProviderProfile (via the duck-typed registry, which
    is `providers/__init__.py`);
  - re-validates capability + privacy independently (defense in depth, fail-closed);
  - honors LOCAL_ONLY (absolute) and ASK_BEFORE_PAID (cost guard);
  - produces a SANITIZED config for the existing transport (key_ref only — never a
    raw secret; the actual key is fetched from agent/secret_sources at call time);
  - fails CLOSED on unknown / incompatible / drifting providers.

Pure module. The registry and candidates are injected (duck-typed) so the whole
thing is unit-testable with no network and no real provider.

DECISÃO ASSUMIDA: candidates (live connection/health/quota/quality) are injected by
the runtime; a `build_candidates()` helper composes them from the catalog + a simple
state map — justificativa: mantém o bridge puro/testável; estado vivo vem do runtime.
DECISÃO ASSUMIDA: the bridge re-checks capability/privacy even though select_provider
already did — justificativa: nunca confiar no chamador; LOCAL_ONLY é absoluto.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence

from agent.provider_adapter import ProviderConfig, sanitize_for_renderer
from agent.provider_catalog import Capability, ProviderCatalog, ProviderEntry
from agent.provider_catalog_link import reconcile
from agent.provider_routing import (
    ProviderCandidate,
    RoutingProfile,
    select_provider,
)


# ---- duck-typed OmniRoute registry (this is providers/__init__.py) ------ #

class _Profile(Protocol):
    name: str
    aliases: tuple
    base_url: str
    signup_url: str
    supports_vision: bool


class _Registry(Protocol):
    def get_provider_profile(self, name: str) -> _Profile | None: ...
    def list_providers(self) -> Sequence[_Profile]: ...


# ---- results ------------------------------------------------------------ #

@dataclass(frozen=True)
class ResolvedProvider:
    """A routing decision resolved to the REAL provider profile + sanitized config.

    `profile` is the opaque, existing ProviderProfile — it is handed straight to the
    existing transport (`_build_kwargs_from_profile`); the bridge never rebuilds it.
    `config` carries NO raw secret (only key_ref / has_key).
    """

    provider_id: str
    profile: object                 # the real ProviderProfile (opaque here)
    api_base: str                   # registry base_url wins (real runtime fact)
    config: ProviderConfig          # sanitized: key_ref only, no api_key field
    reason: str
    is_local: bool
    drift: tuple[str, ...] = ()


@dataclass(frozen=True)
class BridgeOutcome:
    resolved: ResolvedProvider | None
    reason: str
    requires_paid_confirmation: bool = False

    @property
    def ok(self) -> bool:
        return self.resolved is not None

    def sanitized_view(self) -> dict:
        """Renderer/log-safe view — provably free of secrets."""
        if self.resolved is None:
            return {"ok": False, "reason": self.reason,
                    "requires_paid_confirmation": self.requires_paid_confirmation}
        r = self.resolved
        # Renderer gets ONLY {configured, status/metadata} — never the key_ref handle
        # and never a raw secret. sanitize_for_renderer is a final belt-and-suspenders
        # guard in case a secret-bearing field is ever added here by mistake.
        view = {
            "ok": True,
            "provider_id": r.provider_id,
            "api_base": r.api_base,
            "is_local": r.is_local,
            "reason": r.reason,
            "drift": list(r.drift),
            "config": sanitize_for_renderer({
                "provider_id": r.config.provider_id,
                "api_base": r.config.api_base,
                "model": r.config.model,
                "configured": r.config.has_key,   # boolean state only, NOT the ref
            }),
        }
        return view


# ---- candidate construction (helper for the runtime) -------------------- #

def build_candidates(
    catalog: ProviderCatalog,
    *,
    configured: Mapping[str, bool] | None = None,   # provider_id -> a key/config exists
    healthy: Mapping[str, bool] | None = None,       # provider_id -> last health ok
    quality: Mapping[str, float] | None = None,      # provider_id -> benchmark_arena score
    latency_ms: Mapping[str, float] | None = None,
    exhausted: Mapping[str, bool] | None = None,      # free quota exhausted
    include: Sequence[str] | None = None,             # restrict to these ids
) -> list[ProviderCandidate]:
    configured = configured or {}
    healthy = healthy or {}
    quality = quality or {}
    latency_ms = latency_ms or {}
    exhausted = exhausted or {}
    out: list[ProviderCandidate] = []
    for e in catalog.all():
        if include is not None and e.id not in include:
            continue
        # local providers need no key to be "connected"; cloud needs a configured key.
        connected = True if e.is_local else bool(configured.get(e.id, False))
        out.append(ProviderCandidate(
            entry=e,
            connected=connected,
            healthy=bool(healthy.get(e.id, True)),
            free_quota_exhausted=bool(exhausted.get(e.id, False)),
            quality_score=float(quality.get(e.id, 0.6)),
            latency_ms=float(latency_ms.get(e.id, 0.0)),
        ))
    return out


# ---- the bridge --------------------------------------------------------- #

def _resolve_profile(registry: _Registry, entry: ProviderEntry):
    prof = registry.get_provider_profile(entry.id)
    if prof is not None:
        return prof
    # fall back to alias scan (registry.get_provider_profile already resolves aliases,
    # but a catalog id may match only an alias listed on a differently-named profile)
    for p in registry.list_providers():
        if entry.id == getattr(p, "name", None) or entry.id in tuple(getattr(p, "aliases", ())):
            return p
    return None


def route_and_resolve(
    *,
    catalog: ProviderCatalog,
    registry: _Registry,
    candidates: Sequence[ProviderCandidate],
    task_capability: Capability,
    local_only: bool,
    profile: RoutingProfile = RoutingProfile.BALANCED,
    paid_authorized: bool = False,
    key_refs: Mapping[str, str] | None = None,      # provider_id -> secret_source handle
    model: str = "",
) -> BridgeOutcome:
    """Route with the free-first policy, then resolve the REAL provider profile.

    Fails CLOSED: any unknown / incompatible / privacy-violating / drift-blocked
    result returns a BridgeOutcome with resolved=None and a reason.
    """
    key_refs = key_refs or {}

    # 1) normalized routing decision (free-first / LOCAL_ONLY absolute / cost guard)
    decision = select_provider(
        candidates,
        task_capability=task_capability,
        local_only=local_only,
        profile=profile,
        paid_authorized=paid_authorized,
    )
    if decision.provider_id is None:
        return BridgeOutcome(None, decision.reason,
                             requires_paid_confirmation=decision.requires_paid_confirmation)

    entry = catalog.get(decision.provider_id)
    if entry is None:
        return BridgeOutcome(None, f"unknown_catalog_id:{decision.provider_id}")  # fail closed

    # 2) independent re-validation (defense in depth) — never trust the router alone.
    if not entry.has(task_capability):
        return BridgeOutcome(None, f"capability_missing:{task_capability.value}")
    if local_only and not entry.is_local:
        return BridgeOutcome(None, "local_only_violation")            # ABSOLUTE, fail closed

    # 3) resolve the REAL existing ProviderProfile (cloud must have one; local may not).
    rec = reconcile(catalog, registry)
    linked = rec.get(entry.id)
    prof = _resolve_profile(registry, entry)
    if not entry.is_local and prof is None:
        return BridgeOutcome(None, f"unknown_provider:{entry.id}")     # fail closed
    api_base = (linked.api_base if linked is not None else entry.api_base) or entry.api_base
    drift = linked.drift if linked is not None else ()

    # 4) sanitized config for the EXISTING transport — key_ref only, never a raw secret.
    key_ref = key_refs.get(entry.id)
    cfg = ProviderConfig(
        provider_id=entry.id,
        api_base=api_base,
        model=model,
        has_key=(entry.is_local or key_ref is not None),
        key_ref=key_ref,
    )
    resolved = ResolvedProvider(
        provider_id=entry.id,
        profile=prof,               # opaque real profile -> existing transport consumes it
        api_base=api_base,
        config=cfg,
        reason=decision.reason,
        is_local=entry.is_local,
        drift=drift,
    )
    return BridgeOutcome(resolved, "resolved")


__all__ = [
    "ResolvedProvider", "BridgeOutcome", "build_candidates", "route_and_resolve",
]
