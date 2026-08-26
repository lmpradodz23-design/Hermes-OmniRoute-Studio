"""Tests for the doctor health model (§54) + bridge to self-heal."""

from __future__ import annotations

from agent.doctor_model import CheckResult, CheckStatus, DoctorReport
from agent.safe_repair import Health


def _report():
    return DoctorReport((
        CheckResult("gateway", CheckStatus.PASS),
        CheckResult("venv", CheckStatus.FAIL, root_cause="broken symlink",
                    evidence_ref="log:1", repair_candidate="venv"),
        CheckResult("raptor", CheckStatus.BLOCKED, root_cause="binary not installed"),
        CheckResult("mcp", CheckStatus.WARN),
    ))


def test_overall_worst_status_fail_beats_blocked():
    assert _report().overall is CheckStatus.FAIL
    blocked_only = DoctorReport((CheckResult("x", CheckStatus.BLOCKED),
                                 CheckResult("y", CheckStatus.WARN)))
    assert blocked_only.overall is CheckStatus.BLOCKED


def test_failing_blocked_repairable():
    r = _report()
    assert [c.component for c in r.failing()] == ["venv"]
    assert [c.component for c in r.blocked()] == ["raptor"]
    assert [c.component for c in r.repairable()] == ["venv"]


def test_bridge_to_self_heal_signals():
    signals = _report().to_health_signals()
    assert len(signals) == 1
    s = signals[0]
    assert s.component == "venv" and s.health is Health.FAIL
    assert s.detail == "broken symlink"


def test_all_pass_report():
    ok = DoctorReport((CheckResult("a", CheckStatus.PASS), CheckResult("b", CheckStatus.PASS)))
    assert ok.overall is CheckStatus.PASS
    assert ok.failing() == () and ok.to_health_signals() == []
