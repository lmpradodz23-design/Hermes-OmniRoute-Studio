"""Tests for the self-healing loop (§56/§57): isolated, propose-only, bounded."""

from __future__ import annotations

from agent.mission import MissionState
from agent.mission_runtime import NodeOutcome
from agent.mission_store import MissionStore
from agent.safe_repair import Health
from agent.self_heal import HealthSignal, run_self_heal, should_heal
from agent.skill_lifecycle import ProposalState


def _clock():
    box = {"t": 0.0}
    return lambda: (box.__setitem__("t", box["t"] + 1.0) or box["t"])


def test_should_heal_only_on_fail():
    assert should_heal(HealthSignal("gw", Health.FAIL)) is True
    assert should_heal(HealthSignal("gw", Health.WARN)) is False
    assert should_heal(HealthSignal("gw", Health.OK)) is False
    assert should_heal(HealthSignal("gw", Health.BLOCKED)) is False


def test_self_heal_produces_proposal_not_applied(tmp_path):
    store = MissionStore(tmp_path / "m.db")

    def executor(mid, node):   # every stage succeeds
        return NodeOutcome(ok=True, evidence_ref=f"{node}:ok")

    res = run_self_heal(store, HealthSignal("gateway", Health.FAIL, "crash loop"),
                        executor, now_fn=_clock())
    assert res.state is MissionState.COMPLETED
    assert res.proposal is not None
    assert res.proposal.state is ProposalState.PROPOSED   # NOT integrated / not applied
    assert res.proposal.diff_ref.startswith("worktree:")  # isolated
    # the pipeline has no apply-to-production node
    _, dag, statuses = store.load_mission("heal-gateway")
    assert "propose" in dag and not any("apply" in n for n in dag.ids())
    assert statuses["propose"] == "done"
    store.close()


def test_self_heal_patch_failure_is_bounded_no_proposal(tmp_path):
    store = MissionStore(tmp_path / "m.db")

    def executor(mid, node):
        return NodeOutcome(ok=node != "patch_isolated", failure_type="patch failed")

    res = run_self_heal(store, HealthSignal("venv", Health.FAIL), executor,
                        now_fn=_clock(), max_attempts=2)
    assert res.state is MissionState.FAILED     # bounded recovery, then fail
    assert res.proposal is None                 # nothing proposed on failure
    store.close()


def test_security_review_failure_blocks_proposal(tmp_path):
    store = MissionStore(tmp_path / "m.db")

    def executor(mid, node):
        return NodeOutcome(ok=node != "security_review", failure_type="finding")

    res = run_self_heal(store, HealthSignal("mcp", Health.FAIL), executor,
                        now_fn=_clock(), max_attempts=1)
    assert res.state is not MissionState.COMPLETED
    assert res.proposal is None                 # security review must pass to propose
    store.close()


def test_non_fail_signal_does_nothing(tmp_path):
    store = MissionStore(tmp_path / "m.db")
    res = run_self_heal(store, HealthSignal("x", Health.OK),
                        lambda mid, n: NodeOutcome(ok=True), now_fn=_clock())
    assert res.state is MissionState.CANCELLED and res.proposal is None
    store.close()
