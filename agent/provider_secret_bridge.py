"""Provider API keys <-> existing secret_sources bridge (§2 wiring, secret-safe).

Reuses the EXISTING OS-backed secret mechanism (`agent/secret_sources/`) — it does
NOT invent storage, and no raw key is ever persisted in the repo, renderer, logs,
task reports, or screenshots. What the bridge persists is only a NON-SECRET handle
(`ProviderKeyRef`: which env var / source holds the key). The raw value is fetched
at call time, handed to the transport in-process, and never returned to the renderer.

Renderer/main-process boundary: the renderer receives only `KeyState` = {provider_id,
configured, status}. The raw key stays on the Python side.

Pure module: the secret backend is injected via the `SecretResolver` protocol
(duck-typed over `agent/secret_sources` FetchResult), so it is fully unit-testable
with no real vault and no network.

DECISÃO ASSUMIDA: key_ref = (source_name, env_var) — justificativa: casa com o
modelo "mapped" do secret_sources (bind explícito de env var -> ref), que tem
precedência sobre "bulk"; é um handle, não um segredo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol

from agent.provider_adapter import ConnectionStatus

# ErrorKind string values from agent/secret_sources/base.py (stable vocabulary).
_KIND_TO_STATUS: dict[str, ConnectionStatus] = {
    "not_configured": ConnectionStatus.CONFIG_ERROR,
    "binary_missing": ConnectionStatus.CONFIG_ERROR,
    "auth_failed": ConnectionStatus.INVALID_KEY,
    "auth_expired": ConnectionStatus.INVALID_KEY,
    "ref_invalid": ConnectionStatus.CONFIG_ERROR,
    "network": ConnectionStatus.NETWORK_ERROR,
    "empty_value": ConnectionStatus.INVALID_KEY,
    "timeout": ConnectionStatus.NETWORK_ERROR,
    "internal": ConnectionStatus.UNKNOWN,
}


def status_from_error_kind(kind: str | None) -> ConnectionStatus:
    if kind is None:
        return ConnectionStatus.UNKNOWN
    return _KIND_TO_STATUS.get(str(kind), ConnectionStatus.UNKNOWN)


@dataclass(frozen=True)
class ProviderKeyRef:
    """A NON-SECRET handle: which secret source + env var holds the provider's key."""

    provider_id: str
    env_var: str                      # e.g. "GEMINI_API_KEY"
    source: str | None = None         # secret_sources source name (None = default/any)


@dataclass(frozen=True)
class KeyState:
    """Renderer-safe state — NO key, ever."""

    provider_id: str
    configured: bool
    status: ConnectionStatus = ConnectionStatus.UNKNOWN


class _FetchResultLike(Protocol):
    secrets: Mapping[str, str]
    error_kind: object
    @property
    def ok(self) -> bool: ...


class SecretResolver(Protocol):
    """Duck-typed over agent/secret_sources: fetch a mapped env var's value."""

    def fetch_env(self, env_var: str, source: str | None) -> _FetchResultLike: ...


@dataclass(frozen=True)
class ResolvedKey:
    """Result of resolving a provider's key. `_value` is the raw key FOR THE TRANSPORT
    ONLY — it is deliberately private (leading underscore), excluded from renderer
    views, and must never be logged."""

    ok: bool
    status: ConnectionStatus
    _value: str | None = field(default=None, repr=False)   # repr=False: never printed

    def value_for_transport(self) -> str | None:
        """The raw key, for in-process transport use only. Never send to renderer/logs."""
        return self._value


def resolve_key(ref: ProviderKeyRef, resolver: SecretResolver) -> ResolvedKey:
    """Resolve a provider's key via the existing secret backend. Fails safe."""
    try:
        res = resolver.fetch_env(ref.env_var, ref.source)
    except Exception:
        return ResolvedKey(False, ConnectionStatus.UNKNOWN)
    if not getattr(res, "ok", False):
        kind = getattr(res, "error_kind", None)
        kind_str = getattr(kind, "value", kind) if kind is not None else None
        return ResolvedKey(False, status_from_error_kind(kind_str))
    value = dict(getattr(res, "secrets", {}) or {}).get(ref.env_var)
    if not value:
        return ResolvedKey(False, ConnectionStatus.INVALID_KEY)   # empty => treat as invalid
    # ok: key obtained. CONNECTED is decided later by a real health check, not here.
    return ResolvedKey(True, ConnectionStatus.UNKNOWN, _value=value)


class ProviderSecretStore:
    """Persists only NON-SECRET handles (provider_id -> ProviderKeyRef). The renderer
    view exposes only `configured` booleans + status — never a key or even the ref."""

    def __init__(self) -> None:
        self._refs: dict[str, ProviderKeyRef] = {}

    def set_ref(self, ref: ProviderKeyRef) -> None:
        self._refs[ref.provider_id] = ref

    def clear(self, provider_id: str) -> None:
        self._refs.pop(provider_id, None)

    def get_ref(self, provider_id: str) -> ProviderKeyRef | None:
        return self._refs.get(provider_id)

    def is_configured(self, provider_id: str) -> bool:
        return provider_id in self._refs

    def configured_map(self) -> dict[str, bool]:
        return {pid: True for pid in self._refs}

    def renderer_state(self, statuses: Mapping[str, ConnectionStatus] | None = None) -> list[KeyState]:
        """Renderer-safe: {provider_id, configured, status}. No key, no ref."""
        statuses = statuses or {}
        return [
            KeyState(pid, True, statuses.get(pid, ConnectionStatus.UNKNOWN))
            for pid in self._refs
        ]

    def __repr__(self) -> str:  # never leak refs/keys in logs
        return f"ProviderSecretStore(configured={sorted(self._refs)})"


__all__ = [
    "ProviderKeyRef", "KeyState", "SecretResolver", "ResolvedKey",
    "ProviderSecretStore", "resolve_key", "status_from_error_kind",
]
