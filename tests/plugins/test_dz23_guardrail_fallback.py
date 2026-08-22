"""The guardrail must stay conservative when the shared parser is unavailable.

``plugins/dz23-guardrail`` delegates command normalization to
``tools.approval._command_detection_variants``. That import can fail — the
plugin is loaded standalone in tooling, and a partial install or an import-time
error in the core leaves the shared parser unreachable.

The fallback used to return the raw command only. This corpus is the evidence
that such a fallback is not conservative: every case below executes a
destructive verb that the raw string hides from ``_DESTRUCTIVE_PATTERNS``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "dz23-guardrail" / "__init__.py"

# Shell forms that all execute `rm -rf` / `del /s /q` despite the literal text
# not matching a command-boundary-anchored pattern.
HIDDEN_DESTRUCTIVE = [
    r"r\m -rf /tmp/guardrail-fallback",
    "r''m -rf /tmp/guardrail-fallback",
    'r""m -rf /tmp/guardrail-fallback',
    "$(rm -rf /tmp/guardrail-fallback)",
    "`rm -rf /tmp/guardrail-fallback`",
    "$(del /s /q C:\\guardrail-fallback)",
]

# Must NOT block: widening the variant set cannot be allowed to invent matches.
BENIGN = [
    "git clean -n",
    "git clean --dry-run",
    "npm ci",
    "pytest tests/plugins",
    "echo \"nunca rode rm -rf /\" >> notas.txt",
    "type C:\\Users\\me\\notas.txt",
]


def _load_plugin_with_broken_core(monkeypatch: pytest.MonkeyPatch):
    """Load the guardrail with ``tools.approval`` guaranteed to be unimportable."""
    monkeypatch.setitem(sys.modules, "tools.approval", None)
    spec = importlib.util.spec_from_file_location("dz23_guardrail_fallback", PLUGIN)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_fallback_is_actually_active(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard the guard: prove the degraded path is what we are exercising."""
    plugin = _load_plugin_with_broken_core(monkeypatch)
    variants = tuple(plugin._command_detection_variants("rm -rf /tmp/x"))
    assert variants == plugin._standalone_detection_variants("rm -rf /tmp/x")


@pytest.mark.parametrize("command", HIDDEN_DESTRUCTIVE)
def test_hidden_destructive_commands_are_blocked_on_the_fallback_path(
    command: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugin = _load_plugin_with_broken_core(monkeypatch)
    result = plugin.on_pre_tool_call("terminal", {"command": command})
    assert result is not None, f"escapou pelo fallback: {command!r}"
    assert result["action"] == "block", f"nao bloqueou pelo fallback: {command!r}"


@pytest.mark.parametrize("command", BENIGN)
def test_fallback_does_not_invent_matches(
    command: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugin = _load_plugin_with_broken_core(monkeypatch)
    result = plugin.on_pre_tool_call("terminal", {"command": command})
    blocked = bool(result and result.get("action") == "block")
    assert not blocked, f"falso positivo no fallback: {command!r}"


def test_windows_path_is_still_inspected_verbatim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unescaping mangles ``C:\\Users``; the raw variant must survive."""
    plugin = _load_plugin_with_broken_core(monkeypatch)
    variants = plugin._standalone_detection_variants("del /s /q C:\\Users\\me\\docs")
    assert variants[0] == "del /s /q C:\\Users\\me\\docs"
    result = plugin.on_pre_tool_call(
        "terminal", {"command": "del /s /q C:\\Users\\me\\docs"}
    )
    assert result is not None and result["action"] == "block"
