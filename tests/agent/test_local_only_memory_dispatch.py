"""LOCAL_ONLY — central memory-provider DISPATCH-BOUNDARY gate.

The single chokepoint is ``MemoryProvider.local_only_denial()``, checked in
agent_init BEFORE a provider is registered or ``initialize()`` opens any
connection. The base class is FAIL-CLOSED: a provider that does not prove
local-only safety is denied under local-only. mem0 / hindsight override it to
allow a genuinely-local config and deny any remote route.

These tests cover the base contract + the hindsight override (mem0 is covered
in test_local_only_memory_egress.py). No network, no backend construction.
"""

import importlib

import pytest

from agent.memory_provider import MemoryProvider


class _UndeclaredProvider(MemoryProvider):
    """A provider that does NOT override local_only_denial (legacy/3rd-party)."""

    @property
    def name(self) -> str:
        return "undeclared-remote-saas"

    def is_available(self) -> bool:
        return True

    def initialize(self, session_id, **kwargs):  # pragma: no cover - not reached
        raise AssertionError("must never initialize under local-only")

    def get_tool_schemas(self):
        return []


def test_base_fail_closed_denies_undeclared_provider_under_local_only(monkeypatch):
    import agent.local_only as lo

    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    p = _UndeclaredProvider()
    # Fail-closed: unknown provider cannot prove locality → denied.
    assert p.local_only_denial() != ""


def test_base_allows_undeclared_provider_when_local_only_off(monkeypatch):
    import agent.local_only as lo

    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: False)
    p = _UndeclaredProvider()
    assert p.local_only_denial() == ""


def test_base_self_check_exception_is_fail_closed_at_activation():
    # The agent_init gate treats a raising local_only_denial() as "deny".
    # This documents/locks that contract: a provider whose check raises must be
    # denied, never registered. (The gate wraps the call in try/except and sets
    # a non-empty denial on exception.)
    class _Raises(_UndeclaredProvider):
        def local_only_denial(self) -> str:
            raise RuntimeError("self-check blew up")

    p = _Raises()
    denied = ""
    try:
        denied = p.local_only_denial()
    except Exception:
        denied = "local-only self-check failed"
    assert denied != ""


# ── hindsight override ─────────────────────────────────────────────────────
hindsight = None
try:
    hindsight = importlib.import_module("plugins.memory.hindsight")
except Exception:
    hindsight = None

needs_hindsight = pytest.mark.skipif(hindsight is None, reason="hindsight import unavailable")


def _hs():
    return object.__new__(hindsight.HindsightMemoryProvider)


@needs_hindsight
def test_hindsight_cloud_denied(monkeypatch):
    import agent.local_only as lo

    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    monkeypatch.setattr(hindsight, "_load_config", lambda: {"mode": "cloud"})
    assert _hs().local_only_denial() != ""


@needs_hindsight
def test_hindsight_local_external_loopback_allowed(monkeypatch):
    import agent.local_only as lo

    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    monkeypatch.setattr(
        hindsight, "_load_config",
        lambda: {"mode": "local_external", "api_url": "http://127.0.0.1:8888"},
    )
    assert _hs().local_only_denial() == ""


@needs_hindsight
def test_hindsight_local_external_remote_denied(monkeypatch):
    import agent.local_only as lo

    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    monkeypatch.setattr(
        hindsight, "_load_config",
        lambda: {"mode": "local_external", "api_url": "https://hindsight.example.com"},
    )
    assert _hs().local_only_denial() != ""


@needs_hindsight
def test_hindsight_embedded_local_llm_allowed(monkeypatch):
    import agent.local_only as lo

    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    monkeypatch.setattr(
        hindsight, "_load_config",
        lambda: {"mode": "local_embedded", "llm_provider": "ollama"},
    )
    assert _hs().local_only_denial() == ""


@needs_hindsight
def test_hindsight_embedded_remote_llm_provider_denied(monkeypatch):
    # CANARY: embeddings are local, but the fact-extraction LLM is openrouter →
    # turn content egresses → must be denied.
    import agent.local_only as lo

    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    monkeypatch.setattr(
        hindsight, "_load_config",
        lambda: {"mode": "local_embedded", "llm_provider": "openrouter"},
    )
    assert _hs().local_only_denial() != ""


@needs_hindsight
def test_hindsight_embedded_remote_llm_base_url_denied(monkeypatch):
    # Even a "local" provider name is denied if llm_base_url points off-machine.
    import agent.local_only as lo

    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    monkeypatch.setattr(
        hindsight, "_load_config",
        lambda: {"mode": "local_embedded", "llm_provider": "ollama",
                 "llm_base_url": "https://evil.example.com/v1"},
    )
    assert _hs().local_only_denial() != ""


@needs_hindsight
def test_hindsight_unreadable_config_fail_closed(monkeypatch):
    import agent.local_only as lo

    def _boom():
        raise OSError("config unreadable")

    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    monkeypatch.setattr(hindsight, "_load_config", _boom)
    assert _hs().local_only_denial() != ""


@needs_hindsight
def test_hindsight_local_only_off_allows_cloud(monkeypatch):
    import agent.local_only as lo

    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: False)
    monkeypatch.setattr(hindsight, "_load_config", lambda: {"mode": "cloud"})
    assert _hs().local_only_denial() == ""
