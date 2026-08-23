"""LOCAL_ONLY — Supermemory memory egress.

Supermemory is a remote SaaS by default (api.supermemory.ai) with an optional
self-hosted base_url. Under local-only, a remote base URL must be denied (turns/
summaries/memories would leave the machine); a loopback self-hosted server is
allowed.
"""

import importlib

import pytest

sm = None
try:
    sm = importlib.import_module("plugins.memory.supermemory")
except Exception:
    sm = None

needs_sm = pytest.mark.skipif(sm is None, reason="supermemory plugin import unavailable")


def _make():
    return object.__new__(sm.SupermemoryMemoryProvider)


@needs_sm
def test_cloud_default_denied(monkeypatch):
    import agent.local_only as lo

    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    monkeypatch.setattr(sm, "_load_supermemory_config", lambda home: {"base_url": ""})
    assert _make().local_only_denial() != ""


@needs_sm
def test_remote_selfhosted_denied(monkeypatch):
    import agent.local_only as lo

    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    monkeypatch.setattr(
        sm, "_load_supermemory_config", lambda home: {"base_url": "https://memory.example.com"}
    )
    assert _make().local_only_denial() != ""


@needs_sm
def test_loopback_selfhosted_allowed(monkeypatch):
    import agent.local_only as lo

    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    monkeypatch.setattr(
        sm, "_load_supermemory_config", lambda home: {"base_url": "http://localhost:6767"}
    )
    assert _make().local_only_denial() == ""


@needs_sm
def test_env_base_url_denied_when_remote(monkeypatch):
    import agent.local_only as lo

    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    monkeypatch.setattr(sm, "_load_supermemory_config", lambda home: {"base_url": ""})
    monkeypatch.setenv("SUPERMEMORY_BASE_URL", "https://sm.example.net")
    assert _make().local_only_denial() != ""


@needs_sm
def test_local_only_off_allows_cloud(monkeypatch):
    import agent.local_only as lo

    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: False)
    monkeypatch.setattr(sm, "_load_supermemory_config", lambda home: {"base_url": ""})
    assert _make().local_only_denial() == ""


@needs_sm
def test_canary_removing_gate_would_reactivate_cloud(monkeypatch):
    # CANARY: if the override were deleted, the base MemoryProvider fail-closed
    # default would STILL deny cloud supermemory under local-only. Prove the base
    # default denies an undeclared-remote provider so egress can never re-open.
    import agent.local_only as lo
    from agent.memory_provider import MemoryProvider

    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)

    # A provider without a local_only_denial override (simulating the gate removed)
    class _Bare(MemoryProvider):
        @property
        def name(self):
            return "supermemory-bare"

        def is_available(self):
            return True

        def initialize(self, session_id, **kwargs):
            raise AssertionError("must not initialize under local-only")

        def get_tool_schemas(self):
            return []

    assert _Bare().local_only_denial() != ""
