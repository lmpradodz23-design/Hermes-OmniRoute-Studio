"""Tests for the Capability Acquisition Engine (agent/capability_acquisition.py),
including the mandatory §165 gate: a mission needing a missing tool acquires it
autonomously and completes, with no human intervention."""

from __future__ import annotations

from agent.capability_acquisition import (
    AcquisitionDecision,
    AcquisitionEngine,
    AcquisitionPlan,
    AcquisitionRisk,
    AcquisitionState,
    Candidate,
    CapabilityRegistry,
    acquire_node_id,
    classify_block,
    decide,
    inject_acquire_node,
    is_forbidden,
    looks_like_missing_capability,
)
from agent.mission import Mission, MissionState
from agent.mission_dag import DagNode, MissionDag
from agent.mission_runtime import MissionRuntime, NodeOutcome
from agent.mission_store import MissionStore


def _clock():
    box = {"t": 0.0}
    return lambda: (box.__setitem__("t", box["t"] + 1.0) or box["t"])


# ---- detection / classification ----------------------------------------- #


def test_missing_capability_detection():
    for msg in ["rg: command not found", "ModuleNotFoundError: No module named 'x'",
                "browser executable missing", "playwright is not installed"]:
        assert looks_like_missing_capability(msg)
        assert classify_block(msg) == "MISSING_CAPABILITY"
    assert classify_block("the agent keeps looping without progress") == "TASK_STUCK"


# ---- security hard-stop + risk gates ------------------------------------ #


def test_security_hard_stop_forbidden():
    assert is_forbidden(Candidate("m", known_malicious=True))
    assert is_forbidden(Candidate("m", requires_credential=True))
    assert is_forbidden(Candidate("m", from_arbitrary_url=True, signed=False))
    assert is_forbidden(Candidate("m", risk=AcquisitionRisk.HIGH_RISK, signed=False))
    assert decide(Candidate("m", known_malicious=True)) is AcquisitionDecision.FORBIDDEN


def test_risk_gates():
    assert decide(Candidate("a", risk=AcquisitionRisk.LOW_RISK)) is AcquisitionDecision.ACQUIRE
    assert decide(Candidate("a", risk=AcquisitionRisk.MEDIUM_RISK), sandbox_available=True) is (
        AcquisitionDecision.ACQUIRE
    )
    assert decide(Candidate("a", risk=AcquisitionRisk.MEDIUM_RISK), sandbox_available=False) is (
        AcquisitionDecision.HUMAN_GATE
    )
    assert decide(Candidate("a", risk=AcquisitionRisk.HIGH_RISK, signed=True)) is (
        AcquisitionDecision.HUMAN_GATE
    )
    assert decide(Candidate("a", risk=AcquisitionRisk.EXTERNAL)) is (
        AcquisitionDecision.BLOCKED_BY_EXTERNAL_DEPENDENCY
    )
    assert decide(Candidate("a", has_cost=True)) is AcquisitionDecision.HUMAN_GATE
    assert decide(Candidate("a", requires_privilege=True)) is AcquisitionDecision.HUMAN_GATE


# ---- acquire transaction ------------------------------------------------ #


def _plan(name, *, install=True, verify=True, smoke=True, rollback_flag=None, **cand):
    def _rb():
        if rollback_flag is not None:
            rollback_flag.append(name)
    return AcquisitionPlan(
        candidate=Candidate(name, source="official-registry", **cand),
        install=lambda: install, verify=lambda: verify, smoke=lambda: smoke, rollback=_rb,
    )


def test_acquire_success_registers_capability():
    reg = CapabilityRegistry()
    eng = AcquisitionEngine(reg)
    res = eng.acquire("ripgrep", [_plan("rg", version="14.1")])
    assert res.state is AcquisitionState.REGISTERED
    assert reg.has("ripgrep")
    assert res.evidence["smoke"] == "ok"


def test_acquire_rolls_back_then_tries_next_candidate():
    reg = CapabilityRegistry()
    eng = AcquisitionEngine(reg)
    rolled: list[str] = []
    res = eng.acquire(
        "tool",
        [_plan("bad", verify=False, rollback_flag=rolled), _plan("good")],
    )
    assert res.state is AcquisitionState.REGISTERED
    assert "bad" in rolled            # failed candidate rolled back
    assert [t[0] for t in res.tried] == ["bad", "good"]


def test_acquire_all_fail_is_failed():
    reg = CapabilityRegistry()
    res = AcquisitionEngine(reg).acquire("tool", [_plan("a", install=False)])
    assert res.state is AcquisitionState.FAILED
    assert not reg.has("tool")


def test_acquire_human_gate_when_only_gated_candidates():
    reg = CapabilityRegistry()
    res = AcquisitionEngine(reg).acquire(
        "tool", [_plan("paid", has_cost=True), _plan("root", requires_privilege=True)]
    )
    assert res.state is AcquisitionState.HUMAN_GATE
    assert not reg.has("tool")


def test_candidate_limit_is_bounded():
    reg = CapabilityRegistry()
    eng = AcquisitionEngine(reg, candidate_limit=2)
    plans = [_plan(f"c{i}", install=False) for i in range(5)]
    res = eng.acquire("tool", plans)
    assert len(res.tried) == 2       # not infinite


# ---- DAG dynamic node --------------------------------------------------- #


def test_inject_acquire_node():
    dag = MissionDag([DagNode("search"), DagNode("report", parents=("search",))])
    dag2 = inject_acquire_node(dag, "search", "ripgrep")
    acq = acquire_node_id("ripgrep")
    assert acq in dag2
    assert acq in dag2.node("search").parents
    # 'search' is no longer immediately ready — the acquire node must run first
    assert dag2.ready_nodes() == (acq,)
    assert dag2.ready_nodes(done={acq}) == ("search",)


# ---- §165 MANDATORY GATE: autonomous acquire -> resume -> complete ------- #


def test_gate_mission_acquires_missing_tool_and_completes(tmp_path):
    reg = CapabilityRegistry()
    eng = AcquisitionEngine(reg)
    assert not reg.has("ripgrep")   # capability initially missing

    # a mission whose 'search' node needs ripgrep
    base = MissionDag([DagNode("search"), DagNode("report", parents=("search",))])
    dag = inject_acquire_node(base, "search", "ripgrep")

    acq_id = acquire_node_id("ripgrep")

    def executor(mission_id: str, node_id: str) -> NodeOutcome:
        if node_id == acq_id:
            res = eng.acquire("ripgrep", [
                _plan("rg", version="14.1", risk=AcquisitionRisk.LOW_RISK),
            ])
            return NodeOutcome(ok=res.state is AcquisitionState.REGISTERED,
                               evidence_ref="acq:ripgrep")
        if node_id == "search":
            # the original node can only run once the capability is ready
            return NodeOutcome(ok=reg.has("ripgrep"), evidence_ref="search:ok")
        return NodeOutcome(ok=True, evidence_ref=f"{node_id}:ok")

    store = MissionStore(tmp_path / "m.db")
    rt = MissionRuntime(store, executor, now_fn=_clock())
    rt.create(Mission(id="m1", title="find things"), dag)
    final = rt.run("m1")

    assert final is MissionState.COMPLETED     # completed with NO human intervention
    assert reg.has("ripgrep")                  # capability acquired + registered
    _, _, statuses = store.load_mission("m1")
    assert statuses[acq_id] == "done" and statuses["search"] == "done"
    kinds = [e["kind"] for e in store.events("m1")]
    assert kinds.count("node_done") == len(dag)   # acquire + search + report
    store.close()
