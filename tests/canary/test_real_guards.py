"""Register the REAL guards through the canary framework (Wave 6, §8).

Each canary breaks the guard's actual decision data *in memory* (never the
working tree), proves the attack then gets through (RED = harness can detect a
regression), restores it, and proves the attack is blocked (GREEN). If a break
does not actually weaken the guard, the fail-closed framework reports NOT ok.

Guards covered here:
  - LOCAL_ONLY tool egress  (agent.local_only._ALWAYS_REMOTE_TOOL_MARKERS)
  - DZ23 destructive-command guardrail (plugins/dz23-guardrail _DESTRUCTIVE_PATTERNS)
Registering the remaining guards (fork-update guard, update backoff, capability
authorization) through the same driver is the next incremental step.
"""

from __future__ import annotations

import importlib.util
from contextlib import contextmanager
from pathlib import Path

import agent.local_only as lo
from agent.local_only import LocalOnlyConfig, LocalOnlyPolicy
from tests.canary.framework import assert_canary


@contextmanager
def _patched(obj, attr, value):
    """Temporarily replace obj.attr, restoring it afterwards (isolated break)."""
    saved = getattr(obj, attr)
    setattr(obj, attr, value)
    try:
        yield
    finally:
        setattr(obj, attr, saved)


def test_local_only_egress_canary():
    policy = LocalOnlyPolicy(LocalOnlyConfig(enabled=True))

    def attack() -> bool:
        # True == the cloud image tool was BLOCKED under local-only.
        return policy.authorize_tool("image_generate", {}).allowed is False

    result = assert_canary(
        "local_only:image_generate_egress",
        attack=attack,
        # break: remove the always-remote denylist the guard consults.
        break_guard=lambda: _patched(lo, "_ALWAYS_REMOTE_TOOL_MARKERS", ()),
    )
    assert result.ok
    # guard restored: still blocks after the canary.
    assert policy.authorize_tool("image_generate", {}).allowed is False


def _load_guardrail():
    root = Path(__file__).resolve().parents[2]
    init = root / "plugins" / "dz23-guardrail" / "__init__.py"
    spec = importlib.util.spec_from_file_location("dz23_guardrail_canary", init)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_dz23_destructive_command_canary():
    guard = _load_guardrail()

    def attack() -> bool:
        # True == the destructive command was BLOCKED.
        result = guard.on_pre_tool_call("terminal", {"command": "rm -rf /"})
        return bool(result) and result.get("action") == "block"

    result = assert_canary(
        "dz23:destructive_rm_rf_root",
        attack=attack,
        # break: empty the destructive-pattern denylist the guard matches on.
        break_guard=lambda: _patched(guard, "_DESTRUCTIVE_PATTERNS", ()),
    )
    assert result.ok
    # guard restored.
    assert guard.on_pre_tool_call("terminal", {"command": "rm -rf /"})["action"] == "block"
