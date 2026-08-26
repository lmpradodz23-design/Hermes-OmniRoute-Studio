"""Contract tests for the provider <-> secret_sources bridge (§2, secret-safe)."""

from __future__ import annotations

from dataclasses import dataclass, field

from agent.provider_adapter import ConnectionStatus
from agent.provider_secret_bridge import (
    KeyState,
    ProviderKeyRef,
    ProviderSecretStore,
    resolve_key,
    status_from_error_kind,
)


# ---- fakes over agent/secret_sources FetchResult ------------------------ #

@dataclass
class _Kind:
    value: str


@dataclass
class FakeFetch:
    secrets: dict = field(default_factory=dict)
    error: str | None = None
    error_kind: object = None

    @property
    def ok(self) -> bool:
        return self.error is None


class FakeResolver:
    def __init__(self, result=None, raise_exc=False):
        self._result = result
        self._raise = raise_exc

    def fetch_env(self, env_var, source):
        if self._raise:
            raise RuntimeError("backend down")
        return self._result


SECRET = "sk-super-secret-value-xyz"


# ---- resolve_key -------------------------------------------------------- #

def test_resolve_success_gives_key_to_transport_only():
    r = FakeResolver(FakeFetch(secrets={"GEMINI_API_KEY": SECRET}))
    ref = ProviderKeyRef("gemini", "GEMINI_API_KEY", source="command")
    out = resolve_key(ref, r)
    assert out.ok is True
    assert out.value_for_transport() == SECRET     # available in-process for the transport
    assert SECRET not in repr(out)                 # but never printed (repr=False)


def test_resolve_maps_error_kinds_to_status():
    cases = {
        "auth_failed": ConnectionStatus.INVALID_KEY,
        "network": ConnectionStatus.NETWORK_ERROR,
        "timeout": ConnectionStatus.NETWORK_ERROR,
        "not_configured": ConnectionStatus.CONFIG_ERROR,
    }
    for kind, expect in cases.items():
        r = FakeResolver(FakeFetch(error="boom", error_kind=_Kind(kind)))
        out = resolve_key(ProviderKeyRef("x", "X_KEY"), r)
        assert out.ok is False and out.status is expect


def test_resolve_empty_value_is_invalid_key():
    r = FakeResolver(FakeFetch(secrets={}))        # ok but nothing returned
    out = resolve_key(ProviderKeyRef("x", "X_KEY"), r)
    assert out.ok is False and out.status is ConnectionStatus.INVALID_KEY


def test_resolve_backend_exception_fails_safe():
    r = FakeResolver(raise_exc=True)
    out = resolve_key(ProviderKeyRef("x", "X_KEY"), r)
    assert out.ok is False and out.status is ConnectionStatus.UNKNOWN
    assert out.value_for_transport() is None


def test_status_from_error_kind_defaults_unknown():
    assert status_from_error_kind(None) is ConnectionStatus.UNKNOWN
    assert status_from_error_kind("weird_new_kind") is ConnectionStatus.UNKNOWN


# ---- store: handles only, never secrets --------------------------------- #

def test_store_persists_only_nonsecret_handles():
    store = ProviderSecretStore()
    store.set_ref(ProviderKeyRef("gemini", "GEMINI_API_KEY", source="command"))
    assert store.is_configured("gemini") is True
    assert store.is_configured("openai") is False
    assert store.configured_map() == {"gemini": True}

    state = store.renderer_state({"gemini": ConnectionStatus.CONNECTED})
    assert state == [KeyState("gemini", True, ConnectionStatus.CONNECTED)]
    # renderer state carries NO key and NOT the ref/env var
    flat = repr(state) + repr(store)
    assert SECRET not in flat
    assert "GEMINI_API_KEY" not in flat            # env var handle never reaches renderer/logs


def test_store_clear():
    store = ProviderSecretStore()
    store.set_ref(ProviderKeyRef("gemini", "GEMINI_API_KEY"))
    store.clear("gemini")
    assert store.is_configured("gemini") is False
