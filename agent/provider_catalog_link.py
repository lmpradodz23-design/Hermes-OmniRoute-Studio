"""Catalog <-> OmniRoute registry reconciliation (§2/§20/§39 — anti-parallel guard).

The curation catalog (`provider_catalog`) is NOT a second provider registry. The
authoritative runtime provider set is the existing OmniRoute `providers` package
(`ProviderProfile`: base_url / auth_type / supports_vision / signup_url / aliases).
This module *links* the two: it reconciles catalog ids against the live registry,
prefers the registry's real runtime facts over any catalog guess, and flags drift
instead of silently overriding — so the catalog can never fork into a parallel router.

Pure module: the registry is duck-typed (anything exposing ``list_providers()`` and
``get_provider_profile(name)`` returning objects with ``name``/``aliases``/``base_url``/
``signup_url``/``supports_vision``). Real binding to `providers` is a one-line import
at the runtime seam (WAITING_FOR_HUMAN to validate on the app host).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from agent.provider_catalog import Capability, ProviderCatalog, ProviderEntry, Tri


class _Profile(Protocol):
    name: str
    aliases: tuple
    base_url: str
    signup_url: str
    supports_vision: bool


class _Registry(Protocol):
    def list_providers(self) -> Sequence[_Profile]: ...
    def get_provider_profile(self, name: str) -> _Profile | None: ...


@dataclass(frozen=True)
class LinkedProvider:
    """A catalog entry joined to its live runtime profile (if any)."""

    entry: ProviderEntry
    has_runtime_profile: bool
    api_base: str          # registry base_url wins when present (real runtime fact)
    get_key_url: str       # registry signup_url wins when present
    drift: tuple[str, ...] = ()   # human-readable consistency warnings (never silent)

    @property
    def is_executable(self) -> bool:
        # Local providers execute via their own endpoint; cloud needs a runtime profile.
        return self.entry.is_local or self.has_runtime_profile


@dataclass(frozen=True)
class Reconciliation:
    linked: tuple[LinkedProvider, ...]
    catalog_without_runtime: tuple[str, ...]   # curated but no executable profile yet
    registry_without_catalog: tuple[str, ...]  # runtime provider lacking curation metadata

    def get(self, provider_id: str) -> LinkedProvider | None:
        for lp in self.linked:
            if lp.entry.id == provider_id:
                return lp
        return None


def _match_profile(entry: ProviderEntry, registry: _Registry) -> _Profile | None:
    prof = registry.get_provider_profile(entry.id)
    if prof is not None:
        return prof
    # fall back to alias scan
    for p in registry.list_providers():
        if entry.id == getattr(p, "name", None) or entry.id in tuple(getattr(p, "aliases", ())):
            return p
    return None


def reconcile(catalog: ProviderCatalog, registry: _Registry) -> Reconciliation:
    linked: list[LinkedProvider] = []
    matched_runtime_names: set[str] = set()

    for entry in catalog.all():
        prof = _match_profile(entry, registry)
        drift: list[str] = []
        api_base = entry.api_base
        get_key_url = entry.get_key_url

        if prof is not None:
            matched_runtime_names.add(getattr(prof, "name", entry.id))
            # Registry is authoritative for live runtime facts.
            if getattr(prof, "base_url", ""):
                if entry.api_base and entry.api_base.rstrip("/") != prof.base_url.rstrip("/"):
                    drift.append(f"api_base differs (catalog={entry.api_base} registry={prof.base_url})")
                api_base = prof.base_url
            if getattr(prof, "signup_url", ""):
                get_key_url = prof.signup_url
            # Capability sanity: catalog claims VISION but runtime profile denies it.
            if entry.has(Capability.VISION) and getattr(prof, "supports_vision", None) is False:
                drift.append("catalog marks VISION but runtime profile supports_vision=False")

        linked.append(LinkedProvider(
            entry=entry,
            has_runtime_profile=prof is not None,
            api_base=api_base,
            get_key_url=get_key_url,
            drift=tuple(drift),
        ))

    catalog_ids = {e.id for e in catalog.all()}
    catalog_without_runtime = tuple(
        lp.entry.id for lp in linked
        if not lp.entry.is_local and not lp.has_runtime_profile
    )
    registry_names = {getattr(p, "name", "") for p in registry.list_providers()}
    registry_without_catalog = tuple(
        n for n in sorted(registry_names)
        if n and n not in catalog_ids and n not in matched_runtime_names
    )
    return Reconciliation(
        linked=tuple(linked),
        catalog_without_runtime=catalog_without_runtime,
        registry_without_catalog=registry_without_catalog,
    )


__all__ = ["LinkedProvider", "Reconciliation", "reconcile"]
