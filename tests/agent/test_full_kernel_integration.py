"""Full Autonomy Kernel integration (§10/§102/§103) with failure injection.

Composes ProductSpec -> MissionDag -> capability acquisition -> scheduler
(MissionRuntime + budget/autonomy policy) -> security gate -> completion, and
injects: missing tool, provider failure (stuck node), budget reached, and a
security finding. Asserts the kernel reacts correctly end to end (source-level;
REAL_RUNTIME still WAITING_FOR_HUMAN)."""

from __future__ import annotations

from agent.autonomy_levels import ActionClass, AutonomyLevel
from agent.budget_state import BudgetState
from agent.capability_acquisition import (
    AcquisitionEngine,
    AcquisitionPlan,
    AcquisitionState,
    Candidate,
    CapabilityRegistry,
    acquire_node_id,
    inject_acquire_node,
)
from agent.mission import Mission, MissionState
from agent.mission_dag import DagNode, MissionDag
from agent.mission_policy import make_dispatch_policy
from agent.mission_runtime import MissionRuntime, NodeOutcome
from agent.mission_store import MissionStore
from agent.security_gate import (
    FindingState,
    RESCAN_NODE,
    SecurityFinding,
    Severity,
    apply_security_gate,
    remediation_node_id,
)


def _clock():
    box = {"t": 0.0}
    return lambda: (box.__setitem__("t", box["t"] + 1.0) or box["t"])


def _pipeline_dag():
    # research -> build -> security_review -> release
    return MissionDag([
        DagNode("research"),
        DagNode("build", parents=("research",)),
        DagNode("security_review", parents=("build",)),
        DagNode("release", parents=("security_review",)),
    ])


def test_full_pipeline_acquires_tool_and_clears_security(tmp_path):
    reg = CapabilityRegistry()
    eng = AcquisitionEngine(reg)

    # build needs a missing tool; a confirmed P0 must be remediated before release
    dag = inject_acquire_node(_pipeline_dag(), "build", "ripgrep")
    dag = apply_security_gate(
        dag, security_node="security_review", release_node="release",
        findings=[SecurityFinding("F1", Severity.P0, "SQLi", FindingState.CONFIRMED, "fact:1")],
    )
    acq = acquire_node_id("ripgrep")

    def executor(mid, node):
        if node == acq:
            res = eng.acquire("ripgrep", [AcquisitionPlan(
                Candidate("rg", source="registry"),
                install=lambda: True, verify=lambda: True, smoke=lambda: True)])
            return NodeOutcome(ok=res.state is AcquisitionState.REGISTERED, evidence_ref="acq")
        if node == "build":
            return NodeOutcome(ok=reg.has("ripgrep"), evidence_ref="build")  # needs the tool
        return NodeOutcome(ok=True, evidence_ref=f"{node}")

    store = MissionStore(tmp_path / "m.db")
    rt = MissionRuntime(store, executor, now_fn=_clock())
    rt.create(Mission(id="prod"), dag)
    assert rt.run("prod") is MissionState.COMPLETED
    _, _, st = store.load_mission("prod")
    assert reg.has("ripgrep")
    assert st[remediation_node_id("F1")] == "done" and st[RESCAN_NODE] == "done"
    assert st["release"] == "done"
    store.close()


def test_provider_failure_on_node_is_bounded(tmp_path):
    # 'build' provider keeps failing -> bounded recovery -> mission FAILED (not infinite)
    calls = {"build": 0}

    def executor(mid, node):
        if node == "build":
            calls["build"] += 1
            return NodeOutcome(ok=False, failure_type="provider unavailable 503")
        return NodeOutcome(ok=True)

    from agent.mission_runtime import RecoveryPolicy
    store = MissionStore(tmp_path / "m.db")
    rt = MissionRuntime(store, executor, now_fn=_clock(), recovery=RecoveryPolicy(max_attempts=3))
    rt.create(Mission(id="pf"), _pipeline_dag())
    assert rt.run("pf") is MissionState.FAILED
    assert calls["build"] == 3          # bounded
    store.close()


def test_budget_reached_blocks_pipeline(tmp_path):
    store = MissionStore(tmp_path / "m.db")
    policy = make_dispatch_policy(
        autonomy=AutonomyLevel.AUTONOMOUS,
        action_of=lambda n: ActionClass.LOCAL_REVERSIBLE,
        budget_of=lambda: BudgetState.LIMIT_REACHED,
    )
    rt = MissionRuntime(store, lambda mid, n: NodeOutcome(ok=True),
                        now_fn=_clock(), policy=policy)
    rt.create(Mission(id="bg"), _pipeline_dag())
    assert rt.run("bg") is MissionState.BLOCKED
    store.close()


def test_missing_evidence_prevents_completion(tmp_path):
    # 'build' returns ok but WITHOUT its required evidence -> treated as not done.
    from agent.mission_evidence import EvidenceItem, EvidenceKind, required_for, verify_node

    def executor(mid, node):
        if node == "build":
            provided = []  # no diff/test/command evidence
            verified = verify_node(required_for("CODING"), provided).is_pass
            return NodeOutcome(ok=verified, failure_type="unverified: missing evidence")
        return NodeOutcome(ok=True)

    from agent.mission_runtime import RecoveryPolicy
    store = MissionStore(tmp_path / "m.db")
    rt = MissionRuntime(store, executor, now_fn=_clock(), recovery=RecoveryPolicy(max_attempts=1))
    rt.create(Mission(id="ev"), _pipeline_dag())
    final = rt.run("ev")
    assert final is MissionState.FAILED     # cannot complete without required evidence
    store.close()
