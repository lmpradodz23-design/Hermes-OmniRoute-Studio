"""Tests for the unified progress/stuck signal (agent/progress_signal.py)."""

from __future__ import annotations

from agent.progress_signal import (
    ProgressReading,
    ProgressSignal,
    classify,
    is_actionable,
)


def _reading(**kw) -> ProgressReading:
    base = dict(now=1000.0, last_heartbeat_at=1000.0, last_progress_at=1000.0)
    base.update(kw)
    return ProgressReading(**base)


def test_no_heartbeat_is_stalled():
    assert classify(_reading(last_heartbeat_at=None)) is ProgressSignal.STALLED_NO_HEARTBEAT
    # heartbeat older than TTL
    assert (
        classify(_reading(now=2000.0, last_heartbeat_at=1000.0))
        is ProgressSignal.STALLED_NO_HEARTBEAT
    )


def test_progressing_when_workspace_changes_or_fresh():
    assert classify(_reading(workspace_changed=True, no_progress_turns=2)) is (
        ProgressSignal.PROGRESSING
    )
    assert classify(_reading(no_progress_turns=0)) is ProgressSignal.PROGRESSING


def test_heartbeat_only_when_beating_but_not_advancing():
    r = _reading(no_progress_turns=2, workspace_changed=False)
    assert classify(r) is ProgressSignal.HEARTBEAT_ONLY


def test_strategy_change_after_three_same_failures():
    assert classify(_reading(same_failure_count=3)) is (
        ProgressSignal.STRATEGY_CHANGE_REQUIRED
    )


def test_escalate_after_five_no_progress_turns():
    assert classify(_reading(no_progress_turns=5)) is (
        ProgressSignal.ESCALATE_TO_DIAGNOSTIC_AGENT
    )


def test_severity_ordering_escalate_beats_strategy_change():
    # both conditions true -> the more severe (escalate) wins
    r = _reading(no_progress_turns=6, same_failure_count=4)
    assert classify(r) is ProgressSignal.ESCALATE_TO_DIAGNOSTIC_AGENT


def test_stalled_beats_everything():
    r = _reading(last_heartbeat_at=None, no_progress_turns=6, same_failure_count=6)
    assert classify(r) is ProgressSignal.STALLED_NO_HEARTBEAT


def test_thresholds_are_configurable():
    # no_progress_turns>=1 so we don't short-circuit to PROGRESSING; the point is
    # the same_failure_count threshold.
    r = _reading(same_failure_count=2, no_progress_turns=2)
    assert classify(r) is ProgressSignal.HEARTBEAT_ONLY  # default threshold 3
    assert classify(r, strategy_change_after=2) is (
        ProgressSignal.STRATEGY_CHANGE_REQUIRED
    )


def test_is_actionable():
    assert is_actionable(ProgressSignal.STRATEGY_CHANGE_REQUIRED)
    assert is_actionable(ProgressSignal.ESCALATE_TO_DIAGNOSTIC_AGENT)
    assert is_actionable(ProgressSignal.STALLED_NO_HEARTBEAT)
    assert not is_actionable(ProgressSignal.PROGRESSING)
    assert not is_actionable(ProgressSignal.HEARTBEAT_ONLY)
