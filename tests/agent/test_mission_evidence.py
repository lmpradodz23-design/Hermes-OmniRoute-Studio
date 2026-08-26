"""Tests for per-node evidence requirements (agent/mission_evidence.py, §12/§79)."""

from __future__ import annotations

from agent.mission_evidence import (
    EvidenceItem,
    EvidenceKind,
    Verification,
    required_for,
    verify_node,
)


def test_no_requirement_is_verified():
    assert verify_node((), []).status is Verification.VERIFIED
    assert required_for("MICRO") == ()
    assert required_for("unknown-role") == ()


def test_missing_required_evidence_is_unverified_not_pass():
    required = required_for("CODING")  # TEST, DIFF, COMMAND_RESULT
    result = verify_node(required, [EvidenceItem(EvidenceKind.TEST, "ledger:1", ok=True)])
    assert result.status is Verification.UNVERIFIED
    assert not result.is_pass
    assert set(result.missing) == {EvidenceKind.DIFF, EvidenceKind.COMMAND_RESULT}


def test_all_present_and_ok_is_verified():
    required = required_for("CODING")
    provided = [
        EvidenceItem(EvidenceKind.TEST, "ledger:1", ok=True),
        EvidenceItem(EvidenceKind.DIFF, "diff:abc", ok=True),
        EvidenceItem(EvidenceKind.COMMAND_RESULT, "cmd:9", ok=True),
    ]
    r = verify_node(required, provided)
    assert r.status is Verification.VERIFIED
    assert r.is_pass


def test_present_but_failing_is_failed():
    required = (EvidenceKind.TEST,)
    r = verify_node(required, [EvidenceItem(EvidenceKind.TEST, "ledger:1", ok=False)])
    assert r.status is Verification.FAILED
    assert EvidenceKind.TEST in r.failing


def test_release_requires_build_installer_smoke():
    required = required_for("RELEASE")
    assert set(required) == {EvidenceKind.BUILD, EvidenceKind.INSTALLER, EvidenceKind.SMOKE}
    # only a build present -> still UNVERIFIED
    r = verify_node(required, [EvidenceItem(EvidenceKind.BUILD, "b1")])
    assert r.status is Verification.UNVERIFIED
    assert set(r.missing) == {EvidenceKind.INSTALLER, EvidenceKind.SMOKE}


def test_runtime_composition_pattern():
    # Mirrors how the Mission runtime would gate a node: a node marked "done" by
    # its executor is only truly PASS if its required evidence verifies.
    node_role = "SECURITY"
    executor_provided = [EvidenceItem(EvidenceKind.SCAN, "scan:1", ok=True)]  # no rescan yet
    result = verify_node(required_for(node_role), executor_provided)
    node_is_pass = result.is_pass
    assert node_is_pass is False   # security node cannot pass without a rescan
    # after remediation + rescan:
    executor_provided.append(EvidenceItem(EvidenceKind.RESCAN, "scan:2", ok=True))
    assert verify_node(required_for(node_role), executor_provided).is_pass is True
