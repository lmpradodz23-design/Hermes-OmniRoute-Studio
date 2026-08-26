"""Tests for the thin Mission entity (agent/mission.py)."""

from __future__ import annotations

from agent.budget_state import BudgetState
from agent.mission import Checkpoint, Mission, MissionState, derive_state
from agent.progress_signal import ProgressSignal


def test_roundtrip_to_from_dict():
    m = Mission(
        id="m1",
        title="Build SaaS",
        state=MissionState.RUNNING,
        goal_key="goal:sess-1",
        kanban_board_id="board-9",
        created_at=1.0,
        updated_at=2.0,
        human_gate=False,
        meta={"owner": "planner"},
    )
    again = Mission.from_dict(m.to_dict())
    assert again == m


def test_with_state_and_terminal():
    m = Mission(id="m1")
    assert m.state is MissionState.DRAFT
    assert not m.is_terminal()
    done = m.with_state(MissionState.COMPLETED, at=5.0)
    assert done.state is MissionState.COMPLETED
    assert done.updated_at == 5.0
    assert done.is_terminal()
    # original is unchanged (frozen)
    assert m.state is MissionState.DRAFT


def test_checkpoint_is_a_reference_tuple():
    m = Mission(
        id="m1", goal_key="goal:s", kanban_board_id="b", state=MissionState.VERIFYING, updated_at=9.0
    )
    cp = Checkpoint.of(m)
    assert cp.mission_id == "m1"
    assert cp.goal_key == "goal:s"
    assert cp.kanban_board_id == "b"
    assert cp.state is MissionState.VERIFYING
    assert cp.at == 9.0
    assert cp.to_dict()["state"] == "VERIFYING"


def test_derive_state_precedence():
    # cancel/fail win outright
    assert derive_state(total_nodes=3, done_nodes=1, ready_nodes=1, cancelled=True) is (
        MissionState.CANCELLED
    )
    assert derive_state(total_nodes=3, done_nodes=1, ready_nodes=1, failed=True) is (
        MissionState.FAILED
    )
    # human gate / override -> waiting human
    assert derive_state(total_nodes=3, done_nodes=1, ready_nodes=1, awaiting_human=True) is (
        MissionState.WAITING_HUMAN
    )
    assert derive_state(
        total_nodes=3, done_nodes=1, ready_nodes=1, budget=BudgetState.OVERRIDE_REQUIRED
    ) is MissionState.WAITING_HUMAN
    # hard budget breach -> blocked
    assert derive_state(
        total_nodes=3, done_nodes=1, ready_nodes=1, budget=BudgetState.LIMIT_REACHED
    ) is MissionState.BLOCKED
    # all done -> completed
    assert derive_state(total_nodes=3, done_nodes=3, ready_nodes=0) is MissionState.COMPLETED


def test_derive_state_progress_and_frontier():
    # escalate -> repairing ; strategy change -> retrying
    assert derive_state(
        total_nodes=3, done_nodes=1, ready_nodes=1,
        progress=ProgressSignal.ESCALATE_TO_DIAGNOSTIC_AGENT,
    ) is MissionState.REPAIRING
    assert derive_state(
        total_nodes=3, done_nodes=1, ready_nodes=1,
        progress=ProgressSignal.STRATEGY_CHANGE_REQUIRED,
    ) is MissionState.RETRYING
    # work remains but nothing dispatchable -> waiting on dependency
    assert derive_state(total_nodes=3, done_nodes=1, ready_nodes=0) is (
        MissionState.WAITING_DEPENDENCY
    )
    # no nodes yet -> planning
    assert derive_state(total_nodes=0, done_nodes=0, ready_nodes=0) is MissionState.PLANNING
    # healthy running
    assert derive_state(
        total_nodes=3, done_nodes=1, ready_nodes=2, progress=ProgressSignal.PROGRESSING
    ) is MissionState.RUNNING
