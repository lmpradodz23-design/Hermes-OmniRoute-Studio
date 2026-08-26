"""Tests for adaptive pipeline (§67), safe repair (§55), skill lifecycle (§53),
and benchmark arena (§52)."""

from __future__ import annotations

import pytest

from agent.benchmark_arena import rank_models, score
from agent.mission_class import MissionClass, classify, pipeline_gates, security_required
from agent.route_history import RouteRecord
from agent.safe_repair import Health, RepairOutcome, RepairPlan, run_repair
from agent.skill_lifecycle import (
    ImprovementProposal,
    ProposalState,
    SkillRecord,
    SkillState,
    can_promote,
    promote,
)


# ---- adaptive pipeline -------------------------------------------------- #


def test_mission_classification():
    assert classify(files_changed=1) is MissionClass.MICRO
    assert classify(feature_count=1) is MissionClass.STANDARD
    assert classify(feature_count=2) is MissionClass.COMPLEX
    assert classify(is_product=True) is MissionClass.PRODUCT
    assert classify(touches_security=True) is MissionClass.HIGH_RISK


def test_pipeline_scales_but_keeps_mandatory():
    micro = pipeline_gates(MissionClass.MICRO)
    assert "test" in micro and "evidence" in micro
    assert "security" not in micro         # micro doesn't force the whole factory
    assert security_required(MissionClass.STANDARD) is True
    assert set(pipeline_gates(MissionClass.PRODUCT)) >= {"design", "security", "e2e", "release"}


# ---- safe repair -------------------------------------------------------- #


def test_repair_not_needed_when_ok():
    plan = RepairPlan("gateway", diagnose=lambda: Health.OK,
                      repair=lambda: True, verify=lambda: True)
    assert run_repair(plan).outcome is RepairOutcome.NOT_NEEDED


def test_repair_blocked_status():
    plan = RepairPlan("raptor", diagnose=lambda: Health.BLOCKED,
                      repair=lambda: True, verify=lambda: True)
    assert run_repair(plan).outcome is RepairOutcome.BLOCKED


def test_repair_success_minimal_component():
    plan = RepairPlan("venv", diagnose=lambda: Health.FAIL,
                      repair=lambda: True, verify=lambda: True)
    r = run_repair(plan)
    assert r.outcome is RepairOutcome.REPAIRED and r.component == "venv"


def test_repair_hard_stops_without_backup():
    plan = RepairPlan("state_db", diagnose=lambda: Health.FAIL,
                      repair=lambda: True, verify=lambda: True,
                      backup=lambda: False)   # backup refused
    r = run_repair(plan)
    assert r.outcome is RepairOutcome.BLOCKED     # never repair without backup
    assert any("backup=refused" in e for e in r.evidence)


def test_repair_rolls_back_after_attempt_cap():
    # realistic fake: FAIL until rollback restores known-good, then OK.
    state = {"rolled": False}

    def diagnose():
        return Health.OK if state["rolled"] else Health.FAIL

    def rollback():
        state["rolled"] = True
        return True

    plan = RepairPlan("mcp", diagnose=diagnose,
                      repair=lambda: False, verify=lambda: False,
                      rollback=rollback, max_attempts=2)
    r = run_repair(plan)
    assert r.outcome is RepairOutcome.ROLLED_BACK   # repair failed -> safely reverted
    assert r.attempts == 2 and state["rolled"] is True   # bounded, then reverted + verified


# ---- skill lifecycle ---------------------------------------------------- #


def test_promotion_gates():
    draft = SkillRecord("s", origin="agent")
    testing = promote(draft, SkillState.TESTING)
    ok, reason = can_promote(testing, SkillState.APPROVED)
    assert ok is False and "tests" in reason        # no tests yet
    tested = SkillRecord("s", state=SkillState.TESTING, has_tests=True, security_reviewed=True)
    approved = promote(tested, SkillState.APPROVED)
    with pytest.raises(ValueError):
        promote(approved, SkillState.ACTIVE)          # not benchmarked
    benched = SkillRecord("s", state=SkillState.APPROVED, has_tests=True,
                          security_reviewed=True, benchmarked=True)
    assert promote(benched, SkillState.ACTIVE).state is SkillState.ACTIVE


def test_quarantine_always_allowed():
    active = SkillRecord("s", state=SkillState.ACTIVE)
    assert promote(active, SkillState.QUARANTINED).state is SkillState.QUARANTINED


def test_improvement_proposal_needs_independent_approval():
    p = ImprovementProposal("p1", "skill-x", "faster")
    with pytest.raises(ValueError):
        p.integrate()                                 # not reviewed
    assert p.review(True).integrate().state is ProposalState.INTEGRATED
    assert p.review(False).state is ProposalState.REJECTED


# ---- benchmark arena ---------------------------------------------------- #


def test_benchmark_ranking():
    recs = [
        RouteRecord("code", "strong", "p", success=True, verification_score=0.9, retries=0)
        for _ in range(5)
    ] + [
        RouteRecord("code", "weak", "p", success=False, verification_score=0.2, retries=2)
        for _ in range(5)
    ]
    ranked = rank_models(recs, "code")
    assert [s.model for s in ranked] == ["strong", "weak"]
    assert ranked[0].composite > ranked[1].composite
    assert score(recs, "code", "absent") is None
