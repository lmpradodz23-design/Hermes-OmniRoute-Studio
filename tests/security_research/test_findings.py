"""Máquina de estados e dedup de findings — o "verde artificial" barrado."""

import pytest

from security_research.findings import (
    Confidence,
    EvidenceKind,
    Finding,
    FindingState,
    InvalidTransition,
    Severity,
    dedupe,
    fingerprint,
)


def _f(rule="r1", scanner="semgrep", file="a.py", sev=Severity.HIGH, conf=Confidence.MEDIUM):
    return Finding(scanner=scanner, rule=rule, severity=sev, confidence=conf, file=file, line=6)


def test_finding_is_born_candidate():
    assert _f().state == FindingState.CANDIDATE


def test_cannot_jump_candidate_to_confirmed():
    # O atalho exato que a missão proíbe: scanner disse → "confirmado".
    f = _f()
    with pytest.raises(InvalidTransition):
        f.transition(FindingState.CONFIRMED, now=1.0)


def test_confirmed_requires_a_fact():
    f = _f()
    f.transition(FindingState.VALIDATING, now=1.0)
    # sem evidência FACT, não confirma
    with pytest.raises(InvalidTransition, match="FACT"):
        f.transition(FindingState.CONFIRMED, now=2.0)
    f.add_evidence(EvidenceKind.FACT, "reproduzido localmente", "validator")
    f.transition(FindingState.CONFIRMED, now=3.0)
    assert f.state == FindingState.CONFIRMED


def test_fixed_requires_going_through_fixing():
    f = _f()
    f.transition(FindingState.VALIDATING, now=1.0)
    f.add_evidence(EvidenceKind.FACT, "x", "v")
    f.transition(FindingState.CONFIRMED, now=2.0)
    with pytest.raises(InvalidTransition):
        f.transition(FindingState.FIXED, now=3.0)  # pulou FIXING
    f.transition(FindingState.FIXING, now=3.0)
    f.transition(FindingState.FIXED, now=4.0)
    assert f.state == FindingState.FIXED


def test_false_positive_is_terminal_but_not_deleted():
    f = _f()
    f.transition(FindingState.FALSE_POSITIVE, now=1.0)
    # nenhuma transição sai de FALSE_POSITIVE — mas o objeto continua existindo
    with pytest.raises(InvalidTransition):
        f.transition(FindingState.CONFIRMED, now=2.0)


def test_regression_reopens_a_fixed_finding():
    f = _f()
    f.transition(FindingState.VALIDATING, now=1.0)
    f.add_evidence(EvidenceKind.FACT, "x", "v")
    f.transition(FindingState.CONFIRMED, now=2.0)
    f.transition(FindingState.FIXING, now=3.0)
    f.transition(FindingState.FIXED, now=4.0)
    f.transition(FindingState.REGRESSION_FAILED, now=5.0)  # reapareceu
    assert f.state == FindingState.REGRESSION_FAILED


# ── fingerprint / dedup ──────────────────────────────────────────────────


def test_same_problem_different_line_is_one_fingerprint():
    a = fingerprint(scanner="semgrep", rule="r1", normalized_path="src/a.py")
    b = fingerprint(scanner="semgrep", rule="r1", normalized_path="src\\a.py")
    assert a == b  # separador de path normalizado


def test_different_rules_are_different_fingerprints():
    a = fingerprint(scanner="semgrep", rule="r1", normalized_path="a.py")
    b = fingerprint(scanner="semgrep", rule="r2", normalized_path="a.py")
    assert a != b, "regras diferentes no mesmo arquivo NÃO colapsam"


def test_dedupe_keeps_highest_severity_and_merges_evidence():
    low = _f(sev=Severity.LOW)
    low.add_evidence(EvidenceKind.INFERENCE, "pista baixa", "s")
    high = _f(sev=Severity.CRITICAL)
    high.add_evidence(EvidenceKind.FACT, "pista alta", "s")
    result = dedupe([low, high])
    assert len(result) == 1
    assert result[0].severity == Severity.CRITICAL
    # evidência dos dois preservada
    assert len(result[0].evidence) == 2


def test_dedupe_does_not_merge_different_files():
    assert len(dedupe([_f(file="a.py"), _f(file="b.py")])) == 2
