"""Unified progress / stuck signal (Wave 1, §8 Watchdog).

WAVE ZERO found four separate "is it stuck?" clocks — the loop-liveness
watchdog, session-stall notifier, ``goals.classify_progress()``, and the Kanban
claim-TTL reclaim — with no shared mission-level signal. This module is that
shared, pure classifier, modelled on the existing ``goals.classify_progress``
thresholds so a Mission (whether backed by a Goal loop or a Kanban board) has one
stuck signal.

Key distinction preserved from the Goal engine: a *heartbeat* (the loop ran)
is not *progress* (the loop advanced). A run that keeps beating but never
advances is exactly what must escalate. Pure function; no I/O, no wall-clock
read (``now`` is passed in so it stays deterministic and resume-safe).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProgressSignal(str, Enum):
    PROGRESSING = "PROGRESSING"
    HEARTBEAT_ONLY = "HEARTBEAT_ONLY"  # alive, but not advancing (yet)
    STRATEGY_CHANGE_REQUIRED = "STRATEGY_CHANGE_REQUIRED"
    ESCALATE_TO_DIAGNOSTIC_AGENT = "ESCALATE_TO_DIAGNOSTIC_AGENT"
    STALLED_NO_HEARTBEAT = "STALLED_NO_HEARTBEAT"  # loop itself looks dead


# Thresholds mirror the Goal engine's anti-stagnation policy.
DEFAULT_STRATEGY_CHANGE_AFTER = 3   # N equivalent failed attempts
DEFAULT_ESCALATE_AFTER = 5          # N turns with no real progress
DEFAULT_HEARTBEAT_TTL_SECONDS = 180.0


@dataclass(frozen=True)
class ProgressReading:
    """A point-in-time reading for one mission/node.

    All timestamps are epoch seconds. ``last_heartbeat_at`` = last time the loop
    ran at all; ``last_progress_at`` = last time it advanced (tests passed delta,
    task completed, workspace changed usefully). ``no_progress_turns`` and
    ``same_failure_count`` are running counters the engine already maintains.
    """

    now: float
    last_heartbeat_at: float | None = None
    last_progress_at: float | None = None
    no_progress_turns: int = 0
    same_failure_count: int = 0
    workspace_changed: bool = False


def classify(
    reading: ProgressReading,
    *,
    strategy_change_after: int = DEFAULT_STRATEGY_CHANGE_AFTER,
    escalate_after: int = DEFAULT_ESCALATE_AFTER,
    heartbeat_ttl_seconds: float = DEFAULT_HEARTBEAT_TTL_SECONDS,
) -> ProgressSignal:
    """Classify a reading into a single actionable signal.

    Order is by severity (most severe wins), so a run that is simultaneously
    stale and failing reports the most urgent condition:
      1. no heartbeat within TTL  -> STALLED_NO_HEARTBEAT (loop likely dead)
      2. >= escalate_after no-progress turns -> ESCALATE_TO_DIAGNOSTIC_AGENT
      3. >= strategy_change_after same failures -> STRATEGY_CHANGE_REQUIRED
      4. advanced recently / workspace changed -> PROGRESSING
      5. otherwise (beating but not advancing) -> HEARTBEAT_ONLY
    """
    hb = reading.last_heartbeat_at
    if hb is None or (reading.now - hb) > heartbeat_ttl_seconds:
        return ProgressSignal.STALLED_NO_HEARTBEAT

    if escalate_after > 0 and reading.no_progress_turns >= escalate_after:
        return ProgressSignal.ESCALATE_TO_DIAGNOSTIC_AGENT

    if strategy_change_after > 0 and reading.same_failure_count >= strategy_change_after:
        return ProgressSignal.STRATEGY_CHANGE_REQUIRED

    if reading.workspace_changed or reading.no_progress_turns == 0:
        return ProgressSignal.PROGRESSING

    return ProgressSignal.HEARTBEAT_ONLY


def is_actionable(signal: ProgressSignal) -> bool:
    """True when the watchdog must intervene (recover / replan / escalate)."""
    return signal in {
        ProgressSignal.STRATEGY_CHANGE_REQUIRED,
        ProgressSignal.ESCALATE_TO_DIAGNOSTIC_AGENT,
        ProgressSignal.STALLED_NO_HEARTBEAT,
    }


__all__ = [
    "ProgressSignal",
    "ProgressReading",
    "classify",
    "is_actionable",
    "DEFAULT_STRATEGY_CHANGE_AFTER",
    "DEFAULT_ESCALATE_AFTER",
    "DEFAULT_HEARTBEAT_TTL_SECONDS",
]
