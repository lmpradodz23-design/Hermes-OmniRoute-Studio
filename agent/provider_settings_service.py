"""Provider Settings service + guided connect flow + IPC schemas (§3/§4/§10 wiring).

This is the process-side orchestrator the Electron MAIN process calls (the renderer
never touches Python directly). It composes the pure pieces already built:
  catalog + secret store (configured?) + reconcile (executable?) + probes (status) ->
  build_settings_view  ; and a guided CONNECT state machine:
    pick -> validate format -> store (OS secure) -> resolve -> health check -> discover -> CONNECTED.

Secret-safety: an inbound key crosses renderer->main ONCE inside ConnectRequest, is
consumed in-process (validate/store/health), and is NEVER stored here, logged, or
returned. Every outbound object (ConnectResult, the view) is renderer-safe.

All side effects are injected (secret_writer / resolver / http), so the whole flow is
unit-testable with no OS keychain and no network. The real injections are wired on the
app host (= WAITING_FOR_HUMAN). IPC handler shapes are provided as pure dict builders
that the Electron main registers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Mapping

from agent.provider_adapter import ConnectionStatus, user_message, validate_key_format
from agent.provider_catalog import ProviderCatalog
from agent.provider_catalog_link import reconcile
from agent.provider_probe import HttpClient, detect_local, health_check
from agent.provider_secret_bridge import (
    ProviderKeyRef,
    ProviderSecretStore,
    SecretResolver,
    resolve_key,
)
from agent.provider_settings_view import SettingsView, build_settings_view


class ConnectStep(str, Enum):
    VALIDATE_FORMAT = "VALIDATE_FORMAT"
    STORE = "STORE"
    HEALTH_CHECK = "HEALTH_CHECK"
    DISCOVER = "DISCOVER"
    CONNECTED = "CONNECTED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ConnectRequest:
    """renderer -> main, ONE time. `key` is inbound-only and never echoed back."""

    provider_id: str
    key: str = ""


@dataclass(frozen=True)
class ConnectResult:
    """main -> renderer. Renderer-safe: NO key, ever."""

    provider_id: str
    step: ConnectStep
    status: ConnectionStatus
    message: str
    models: tuple[str, ...] = field(default_factory=tuple)
    get_key_url: str = ""

    @property
    def connected(self) -> bool:
        return self.step is ConnectStep.CONNECTED


# secret_writer: writes the raw key to the OS-backed secure store and returns a
# NON-SECRET handle. It must never log/return the key. Injected (real one = keychain).
SecretWriter = Callable[[str, str], ProviderKeyRef]


class ProviderSettingsService:
    def __init__(self, catalog: ProviderCatalog, store: ProviderSecretStore, registry) -> None:
        self._cat = catalog
        self._store = store
        self._registry = registry

    # ---- the Settings -> AI & Models screen data --------------------- #

    def build_view(self, *, statuses: Mapping[str, ConnectionStatus] | None = None,
                   local_only: bool = False) -> SettingsView:
        rec = reconcile(self._cat, self._registry)
        executable = {lp.entry.id: lp.is_executable for lp in rec.linked}
        return build_settings_view(
            self._cat,
            configured=self._store.configured_map(),
            statuses=statuses or {},
            executable=executable,
            local_only=local_only,
        )

    # ---- guided connect flow ----------------------------------------- #

    def connect(self, request: ConnectRequest, *, secret_writer: SecretWriter,
                resolver: SecretResolver, http: HttpClient,
                local_only: bool = False) -> ConnectResult:
        entry = self._cat.get(request.provider_id)
        if entry is None:
            return ConnectResult(request.provider_id, ConnectStep.FAILED,
                                 ConnectionStatus.CONFIG_ERROR, "Unknown provider.")

        # local providers: no key, just detect (LOCAL_ONLY-safe by construction)
        if entry.is_local:
            pr = detect_local(entry.id, http=http)
            step = ConnectStep.CONNECTED if pr.status is ConnectionStatus.CONNECTED else ConnectStep.FAILED
            return ConnectResult(entry.id, step, pr.status, user_message(pr.status),
                                 models=pr.models, get_key_url="")

        # LOCAL_ONLY forbids configuring any cloud provider — fail closed.
        if local_only:
            return ConnectResult(entry.id, ConnectStep.FAILED, ConnectionStatus.CONFIG_ERROR,
                                 "Local-only mode is on: cloud providers are disabled.",
                                 get_key_url=entry.get_key_url)

        # 1) client-side format check (cheap, before any network/store)
        if not validate_key_format(entry.id, request.key):
            return ConnectResult(entry.id, ConnectStep.VALIDATE_FORMAT, ConnectionStatus.INVALID_KEY,
                                 "The API key format looks wrong — double-check it.",
                                 get_key_url=entry.get_key_url)

        # 2) store the raw key in the OS secure store (injected); keep only the handle
        try:
            ref = secret_writer(entry.id, request.key)
        except Exception:
            return ConnectResult(entry.id, ConnectStep.STORE, ConnectionStatus.CONFIG_ERROR,
                                 "Couldn't save the key securely.", get_key_url=entry.get_key_url)
        self._store.set_ref(ref)

        # 3) resolve it back (confirm retrievable) — raw value stays in-process
        resolved = resolve_key(ref, resolver)
        if not resolved.ok:
            return ConnectResult(entry.id, ConnectStep.HEALTH_CHECK, resolved.status,
                                 user_message(resolved.status), get_key_url=entry.get_key_url)

        # 4) real health check + 5) model discovery (key used in-process only)
        pr = health_check(entry.id, entry.api_base, http=http,
                          key=resolved.value_for_transport())
        if pr.status is not ConnectionStatus.CONNECTED:
            return ConnectResult(entry.id, ConnectStep.HEALTH_CHECK, pr.status,
                                 user_message(pr.status), get_key_url=entry.get_key_url)
        return ConnectResult(entry.id, ConnectStep.CONNECTED, ConnectionStatus.CONNECTED,
                             "Connected.", models=pr.models, get_key_url=entry.get_key_url)

    # ---- bulk actions ------------------------------------------------- #

    def test_all(self, *, resolver: SecretResolver, http: HttpClient,
                 local_only: bool = False) -> dict[str, ConnectionStatus]:
        """Health-check every configured provider (+ detect locals). No paid calls."""
        out: dict[str, ConnectionStatus] = {}
        for e in self._cat.all():
            if e.is_local:
                out[e.id] = detect_local(e.id, http=http).status
                continue
            if local_only or not self._store.is_configured(e.id):
                continue
            ref = self._store.get_ref(e.id)
            resolved = resolve_key(ref, resolver) if ref else None
            if resolved is None or not resolved.ok:
                out[e.id] = resolved.status if resolved else ConnectionStatus.CONFIG_ERROR
                continue
            out[e.id] = health_check(e.id, e.api_base, http=http,
                                     key=resolved.value_for_transport()).status
        return out

    def best_free_options(self, *, local_only: bool = False) -> list[str]:
        """Ids for the "Configure best free options" action — free/no-card + locals."""
        ids = [e.id for e in self._cat.filter(local=True)]
        if not local_only:
            ids += [e.id for e in self._cat.all()
                    if not e.is_local and e.no_card and e.free_tier.value == "YES"]
        return ids


# ---- IPC handler contracts (pure dict builders the Electron main registers) --- #

def ipc_get_view(service: ProviderSettingsService, payload: Mapping[str, object]) -> dict:
    statuses = {k: ConnectionStatus(v) for k, v in
                (payload.get("statuses") or {}).items()}  # type: ignore[union-attr]
    view = service.build_view(statuses=statuses, local_only=bool(payload.get("local_only")))
    # SettingsView is already renderer-safe; return a plain nested dict.
    return {
        "quick_start_provider_id": view.quick_start_provider_id,
        "quick_start_reason": view.quick_start_reason,
        "local_only": view.local_only,
        "sections": [
            {"key": s.key, "title": s.title, "subtitle": s.subtitle,
             "cards": [_card_dict(c) for c in s.cards]}
            for s in view.sections
        ],
    }


def _card_dict(c) -> dict:
    return {
        "id": c.id, "name": c.name, "category": c.category, "badges": list(c.badges),
        "capabilities": list(c.capabilities), "connected": c.connected, "status": c.status,
        "status_message": c.status_message, "has_key": c.has_key, "needs_key": c.needs_key,
        "get_key_url": c.get_key_url, "docs_link": c.docs_link, "executable": c.executable,
        "guided_steps": [{"order": s.order, "title": s.title, "detail": s.detail, "href": s.href}
                         for s in c.guided_steps],
    }


__all__ = [
    "ConnectStep", "ConnectRequest", "ConnectResult", "SecretWriter",
    "ProviderSettingsService", "ipc_get_view",
]
