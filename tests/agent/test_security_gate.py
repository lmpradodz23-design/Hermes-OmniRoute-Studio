"""Tests for the security mission gate (Wave 5, §47/§84/§85), incl. a DAG E2E."""

from __future__ import annotations

from agent.mission import Mission, MissionState
from agent.mission_dag import DagNode, MissionDag
from agent.mission_runtime import MissionRuntime, NodeOutcome
from agent.mission_store import MissionStore
from agent.security_gate import (
    FindingState,
    RESCAN_NODE,
    SecurityFinding,
    Severity,
    apply_security_gate,
    release_blocked,
    remediation_node_id,
    rescan,
    validate,
)


def _clock():
    box = {"t": 0.0}
    return lambda: (box.__setitem__("t", box["t"] + 1.0) or box["t"])


def _confirmed_p0(fid="F1"):
    return SecurityFinding(fid, Severity.P0, "SQLi", FindingState.CONFIRMED, evidence_ref="fact:1")


def test_confirmation_requires_evidence():
    no_ev = SecurityFinding("F", Severity.P0, state=FindingState.CONFIRMED)  # no evidence_ref
    assert no_ev.is_confirmed is False
    assert validate([no_ev]) == ()
    assert validate([_confirmed_p0()]) == (_confirmed_p0(),)


def test_release_blocked_by_open_p0():
    assert release_blocked([_confirmed_p0()]) is True
    resolved = SecurityFinding("F1", Severity.P0, state=FindingState.RESOLVED, evidence_ref="x")
    assert release_blocked([resolved]) is False
    assert release_blocked([SecurityFinding("F2", Severity.P3)]) is False  # low sev never blocks


def _base_dag():
    return MissionDag([
        DagNode("build"),
        DagNode("security_review", parents=("build",)),
        DagNode("release", parents=("build",)),
    ])


def test_apply_gate_injects_remediation_and_rescan():
    dag = apply_security_gate(_base_dag(), security_node="security_review",
                              release_node="release", findings=[_confirmed_p0()])
    rid = remediation_node_id("F1")
    assert rid in dag and RESCAN_NODE in dag
    assert dag.node(rid).parents == ("security_review",)
    assert set(dag.node(RESCAN_NODE).parents) == {rid}
    assert RESCAN_NODE in dag.node("release").parents   # release now waits on rescan


def test_no_blocking_findings_is_noop():
    dag = _base_dag()
    same = apply_security_gate(dag, security_node="security_review",
                               release_node="release", findings=[SecurityFinding("x", Severity.P3)])
    assert same.ids() == dag.ids()


def test_rescan_reopens_persisting_finding():
    prev = [_confirmed_p0("F1")]
    still_there = [_confirmed_p0("F1")]         # same finding still confirmed
    assert rescan(prev, still_there) == (_confirmed_p0("F1"),)   # reopens
    cleared: list[SecurityFinding] = []
    assert rescan(prev, cleared) == ()          # gone -> cleared


def test_security_gate_dag_e2e(tmp_path):
    # build -> security_review (finds P0) -> remediation -> rescan -> release
    dag = apply_security_gate(_base_dag(), security_node="security_review",
                              release_node="release", findings=[_confirmed_p0()])

    def executor(mission_id, node_id):
        return NodeOutcome(ok=True, evidence_ref=f"{node_id}:ok")

    store = MissionStore(tmp_path / "m.db")
    rt = MissionRuntime(store, executor, now_fn=_clock())
    rt.create(Mission(id="rel"), dag)
    final = rt.run("rel")
    assert final is MissionState.COMPLETED
    _, _, statuses = store.load_mission("rel")
    # release only completed after remediation + rescan
    assert statuses[remediation_node_id("F1")] == "done"
    assert statuses[RESCAN_NODE] == "done"
    assert statuses["release"] == "done"
    store.close()
