"""Tests for scheduler dispatch enforcement (§8/§9/§60): budget + autonomy gate
wired into the MissionRuntime."""

from __future__ import annotations

from agent.autonomy_levels import ActionClass, AutonomyLevel
from agent.budget_state import BudgetState
from agent.mission import Mission, MissionState
from agent.mission_dag import DagNode, MissionDag
from agent.mission_policy import make_dispatch_policy
from agent.mission_runtime import MissionRuntime, NodeOutcome
from agent.mission_store import MissionStore


def _clock():
    box = {"t": 0.0}
    return lambda: (box.__setitem__("t", box["t"] + 1.0) or box["t"])


def _dag():
    return MissionDag([DagNode("a"), DagNode("b", parents=("a",))])


def _ok_exec(mid, node):
    return NodeOutcome(ok=True, evidence_ref=f"{node}:ok")


def test_no_policy_runs_normally(tmp_path):
    store = MissionStore(tmp_path / "m.db")
    rt = MissionRuntime(store, _ok_exec, now_fn=_clock())
    rt.create(Mission(id="m"), _dag())
    assert rt.run("m") is MissionState.COMPLETED   # default = allow all (unchanged)
    store.close()


def test_budget_limit_blocks_dispatch(tmp_path):
    store = MissionStore(tmp_path / "m.db")
    policy = make_dispatch_policy(
        autonomy=AutonomyLevel.AUTONOMOUS,
        action_of=lambda n: ActionClass.LOCAL_REVERSIBLE,
        budget_of=lambda: BudgetState.LIMIT_REACHED,
    )
    rt = MissionRuntime(store, _ok_exec, now_fn=_clock(), policy=policy)
    rt.create(Mission(id="m"), _dag())
    assert rt.run("m") is MissionState.BLOCKED     # hard budget breach -> not dispatched
    events = [e["kind"] for e in store.events("m")]
    assert "node_denied" in events
    store.close()


def test_budget_override_requires_human(tmp_path):
    store = MissionStore(tmp_path / "m.db")
    policy = make_dispatch_policy(
        autonomy=AutonomyLevel.AUTONOMOUS,
        action_of=lambda n: ActionClass.LOCAL_REVERSIBLE,
        budget_of=lambda: BudgetState.OVERRIDE_REQUIRED,
    )
    rt = MissionRuntime(store, _ok_exec, now_fn=_clock(), policy=policy)
    rt.create(Mission(id="m"), _dag())
    assert rt.run("m") is MissionState.WAITING_HUMAN
    store.close()


def test_autonomy_gates_external_action(tmp_path):
    store = MissionStore(tmp_path / "m.db")
    # EXECUTE level: an external action must be human-gated at dispatch.
    policy = make_dispatch_policy(
        autonomy=AutonomyLevel.EXECUTE,
        action_of=lambda n: ActionClass.EXTERNAL_IRREVERSIBLE,
    )
    rt = MissionRuntime(store, _ok_exec, now_fn=_clock(), policy=policy)
    rt.create(Mission(id="m"), _dag())
    assert rt.run("m") is MissionState.WAITING_HUMAN
    events = [e["kind"] for e in store.events("m")]
    assert "node_human_gate" in events
    store.close()


def test_autonomy_allows_local_action(tmp_path):
    store = MissionStore(tmp_path / "m.db")
    policy = make_dispatch_policy(
        autonomy=AutonomyLevel.AUTONOMOUS,
        action_of=lambda n: ActionClass.LOCAL_IRREVERSIBLE,
    )
    rt = MissionRuntime(store, _ok_exec, now_fn=_clock(), policy=policy)
    rt.create(Mission(id="m"), _dag())
    assert rt.run("m") is MissionState.COMPLETED
    store.close()
