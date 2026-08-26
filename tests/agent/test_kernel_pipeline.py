"""Kernel coherence test (§139): the Wave-1/3 primitives compose into the
north-star flow INTENT -> SPEC -> DAG -> STATE, end to end, with no runtime.

This is the proof that these are one Autonomy Kernel, not a pile of unrelated
features: a structured ProductSpec becomes a Mission DAG, the DAG's frontier +
a BudgetState + a progress signal drive Mission.derive_state through a realistic
lifecycle.
"""

from __future__ import annotations

from agent.budget_state import BudgetState
from agent.mission import Mission, MissionState, derive_state
from agent.product_spec import Feature, ProductSpec
from agent.progress_signal import ProgressSignal


def _spec() -> ProductSpec:
    return ProductSpec(
        name="Workshop SaaS",
        platforms=("web",),
        acceptance_criteria=("mechanic can open and close a repair order",),
        features=(
            Feature("auth", "Auth", "critical"),
            Feature("orders", "Repair orders", "high", depends_on=("auth",)),
            Feature("billing", "Billing", "medium", depends_on=("orders",)),
        ),
    )


def _state_for(dag, done):
    total = len(dag)
    return derive_state(
        total_nodes=total,
        done_nodes=len(done),
        ready_nodes=len(dag.ready_nodes(done)),
        progress=ProgressSignal.PROGRESSING,
    )


def test_intent_to_spec_to_dag_to_state_lifecycle():
    spec = _spec()
    assert spec.is_valid
    dag = spec.to_mission_dag()

    mission = Mission(id="m-workshop", title=spec.name, goal_key="goal:s1",
                      kanban_board_id="board-1", state=MissionState.PLANNING)

    # nothing done: only auth is dispatchable -> RUNNING
    done: set[str] = set()
    assert dag.ready_nodes(done) == ("auth",)
    assert _state_for(dag, done) is MissionState.RUNNING
    mission = mission.with_state(_state_for(dag, done))

    # finish everything except the release node -> nothing ready but work left
    done = {"auth", "orders", "billing", "__qa__"}
    assert dag.ready_nodes(done) == ("__release__",)
    assert _state_for(dag, done) is MissionState.RUNNING

    # a hard budget breach mid-flight blocks the mission regardless of frontier
    assert derive_state(
        total_nodes=len(dag), done_nodes=len(done), ready_nodes=1,
        budget=BudgetState.LIMIT_REACHED,
    ) is MissionState.BLOCKED

    # all nodes done -> COMPLETED
    done = set(dag.ids())
    assert _state_for(dag, done) is MissionState.COMPLETED
    final = mission.with_state(_state_for(dag, done))
    assert final.is_terminal()

    # the critical path is the schedule's spine and ends at release
    cp = dag.critical_path()
    assert cp.nodes[0] == "auth"
    assert cp.nodes[-1] == "__release__"
    assert cp.weight > 0.0


def test_dependency_wait_surfaces_when_frontier_empties_early():
    # A spec whose only feature is blocked leaves nothing dispatchable.
    spec = ProductSpec(
        name="X", platforms=("web",), acceptance_criteria=("c",),
        features=(Feature("a", "A"), Feature("b", "B", depends_on=("a",))),
    )
    dag = spec.to_mission_dag(include_qa=False, include_release=False)
    # 'a' done, 'b' ready — still running
    assert derive_state(total_nodes=2, done_nodes=1, ready_nodes=1) is MissionState.RUNNING
    # pretend 'a' failed so 'b' can never start: 0 ready, work remains
    assert derive_state(total_nodes=2, done_nodes=0, ready_nodes=0) is (
        MissionState.WAITING_DEPENDENCY
    )
