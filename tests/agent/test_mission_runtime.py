"""Tests for Mission orchestration + persistence (agent/mission_runtime.py,
agent/mission_store.py): scheduling, checkpoint/restart/resume, bounded recovery,
and the watchdog verdicts."""

from __future__ import annotations

import pytest

from agent.mission import Mission, MissionState
from agent.mission_dag import DagNode, MissionDag
from agent.mission_runtime import (
    DONE,
    FAILED,
    MissionRuntime,
    NodeOutcome,
    RecoveryPolicy,
    RUNNING,
    WatchdogStatus,
    watchdog,
)
from agent.mission_store import MissionStore
from agent.progress_signal import ProgressSignal
from agent.product_spec import Feature, ProductSpec


def _clock():
    box = {"t": 0.0}

    def now() -> float:
        box["t"] += 1.0
        return box["t"]

    return now


def _dag() -> MissionDag:
    # a -> b -> c  (linear), plus d depending on a
    return MissionDag(
        [
            DagNode("a"),
            DagNode("b", parents=("a",)),
            DagNode("c", parents=("b",)),
            DagNode("d", parents=("a",)),
        ]
    )


class _Executor:
    """Completes nodes; specific nodes can be made to fail a number of times."""

    def __init__(self, fail_times: dict[str, int] | None = None,
                 always_fail: set[str] | None = None):
        self.fail_times = dict(fail_times or {})
        self.always_fail = set(always_fail or ())
        self.calls: list[str] = []

    def __call__(self, mission_id: str, node_id: str) -> NodeOutcome:
        self.calls.append(node_id)
        if node_id in self.always_fail:
            return NodeOutcome(ok=False, failure_type="boom")
        if self.fail_times.get(node_id, 0) > 0:
            self.fail_times[node_id] -= 1
            return NodeOutcome(ok=False, failure_type="flaky")
        return NodeOutcome(ok=True, evidence_ref=f"evi:{node_id}")


def test_happy_path_runs_to_completion(tmp_path):
    store = MissionStore(tmp_path / "m.db")
    rt = MissionRuntime(store, _Executor(), now_fn=_clock())
    m = Mission(id="m1", title="demo", goal_key="goal:s", kanban_board_id="b1")
    rt.create(m, _dag())
    final = rt.run("m1")
    assert final is MissionState.COMPLETED
    _, _, statuses = store.load_mission("m1")
    assert all(s == DONE for s in statuses.values())
    # events + checkpoint persisted
    kinds = [e["kind"] for e in store.events("m1")]
    assert "created" in kinds and kinds.count("node_done") == 4
    assert store.load_checkpoint("m1").state is MissionState.COMPLETED
    store.close()


def test_persistence_survives_restart_and_resumes(tmp_path):
    db = tmp_path / "m.db"
    store = MissionStore(db)
    rt = MissionRuntime(store, _Executor(), now_fn=_clock())
    rt.create(Mission(id="m1"), _dag())
    rt.tick("m1")  # completes 'a'
    rt.tick("m1")  # completes one of b/d
    _, _, mid_statuses = store.load_mission("m1")
    assert mid_statuses["a"] == DONE
    assert any(s == DONE for s in mid_statuses.values())
    assert any(s == "pending" for s in mid_statuses.values())
    store.close()  # simulate process exit

    # fresh process: reopen the same DB, resume
    store2 = MissionStore(db)
    _, _, reloaded = store2.load_mission("m1")
    assert reloaded["a"] == DONE  # state truly persisted across the boundary
    rt2 = MissionRuntime(store2, _Executor(), now_fn=_clock())
    final = rt2.resume("m1")
    assert final is MissionState.COMPLETED
    _, _, statuses = store2.load_mission("m1")
    assert all(s == DONE for s in statuses.values())
    store2.close()


def test_bounded_recovery_no_infinite_retry(tmp_path):
    store = MissionStore(tmp_path / "m.db")
    ex = _Executor(always_fail={"b"})
    rt = MissionRuntime(store, ex, now_fn=_clock(), recovery=RecoveryPolicy(max_attempts=3))
    rt.create(Mission(id="m1"), _dag())
    final = rt.run("m1", max_ticks=100)
    assert final is MissionState.FAILED
    row = store.node_row("m1", "b")
    assert row["status"] == FAILED
    assert row["attempts"] == 3           # retried exactly max_attempts, then failed
    assert ex.calls.count("b") == 3       # not infinite
    store.close()


def test_flaky_node_recovers_within_budget(tmp_path):
    store = MissionStore(tmp_path / "m.db")
    ex = _Executor(fail_times={"c": 2})   # fails twice then succeeds
    rt = MissionRuntime(store, ex, now_fn=_clock(), recovery=RecoveryPolicy(max_attempts=5))
    rt.create(Mission(id="m1"), _dag())
    final = rt.run("m1")
    assert final is MissionState.COMPLETED
    assert store.node_row("m1", "c")["attempts"] == 3   # 2 fails + 1 success
    store.close()


def test_resume_resets_crashed_running_node(tmp_path):
    store = MissionStore(tmp_path / "m.db")
    rt = MissionRuntime(store, _Executor(), now_fn=_clock())
    rt.create(Mission(id="m1"), _dag())
    # simulate a crash: 'a' stuck in RUNNING
    store.set_node_status("m1", "a", RUNNING)
    final = rt.resume("m1")
    assert final is MissionState.COMPLETED
    assert any(e["kind"] == "resume_reset_running" for e in store.events("m1"))
    store.close()


def test_from_product_spec_dag(tmp_path):
    spec = ProductSpec(
        name="Clinic", platforms=("web",), acceptance_criteria=("book",),
        features=(Feature("auth", "Auth", "critical"),
                  Feature("book", "Booking", "high", depends_on=("auth",))),
    )
    store = MissionStore(tmp_path / "m.db")
    rt = MissionRuntime(store, _Executor(), now_fn=_clock())
    rt.create(Mission(id="clinic", title=spec.name), spec.to_mission_dag())
    assert rt.run("clinic") is MissionState.COMPLETED
    _, _, statuses = store.load_mission("clinic")
    assert statuses["__release__"] == DONE
    store.close()


def test_watchdog_verdicts():
    assert watchdog(progress=ProgressSignal.PROGRESSING, any_failed=False,
                    recoverable=False, awaiting_human=False).status is WatchdogStatus.HEALTHY
    assert watchdog(progress=ProgressSignal.PROGRESSING, any_failed=False,
                    recoverable=False, awaiting_human=True).status is WatchdogStatus.BLOCKED
    assert watchdog(progress=ProgressSignal.PROGRESSING, any_failed=True,
                    recoverable=True, awaiting_human=False).action == "retry"
    assert watchdog(progress=ProgressSignal.PROGRESSING, any_failed=True,
                    recoverable=False, awaiting_human=False).status is WatchdogStatus.FAILED
    assert watchdog(progress=ProgressSignal.STALLED_NO_HEARTBEAT, any_failed=False,
                    recoverable=False, awaiting_human=False).status is WatchdogStatus.STUCK
    assert watchdog(progress=ProgressSignal.STRATEGY_CHANGE_REQUIRED, any_failed=False,
                    recoverable=False, awaiting_human=False).status is WatchdogStatus.RECOVERABLE
