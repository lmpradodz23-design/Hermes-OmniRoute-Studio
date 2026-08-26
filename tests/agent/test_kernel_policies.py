"""Tests for Wave-1 kernel policies: autonomy levels, failure taxonomy, idempotency."""

from __future__ import annotations

from agent.autonomy_levels import ActionClass, AutonomyLevel, Decision, decide
from agent.failure_taxonomy import FailureType, classify, recommended_action
from agent.idempotency import IdempotencyStore, OperationKey, run_once


# ---- autonomy levels ---------------------------------------------------- #


def test_always_gated_actions_gate_at_every_level():
    for level in AutonomyLevel:
        for action in (ActionClass.DESTRUCTIVE, ActionClass.FINANCIAL,
                       ActionClass.RELEASE_PUBLISH, ActionClass.SECRET_ROTATION):
            assert decide(level, action) is Decision.HUMAN_GATE


def test_assist_proposes_non_readonly():
    assert decide(AutonomyLevel.ASSIST, ActionClass.READ_ONLY) is Decision.ALLOW
    assert decide(AutonomyLevel.ASSIST, ActionClass.LOCAL_REVERSIBLE) is Decision.PROPOSE


def test_execute_allows_local_reversible_only():
    assert decide(AutonomyLevel.EXECUTE, ActionClass.LOCAL_REVERSIBLE) is Decision.ALLOW
    assert decide(AutonomyLevel.EXECUTE, ActionClass.LOCAL_IRREVERSIBLE) is Decision.HUMAN_GATE
    assert decide(AutonomyLevel.EXECUTE, ActionClass.EXTERNAL_REVERSIBLE) is Decision.HUMAN_GATE


def test_autonomous_allows_local_gates_external():
    assert decide(AutonomyLevel.AUTONOMOUS, ActionClass.LOCAL_IRREVERSIBLE) is Decision.ALLOW
    assert decide(AutonomyLevel.AUTONOMOUS, ActionClass.EXTERNAL_REVERSIBLE) is Decision.HUMAN_GATE


def test_production_guarded_allows_external_reversible_gates_irreversible():
    assert decide(AutonomyLevel.PRODUCTION_GUARDED, ActionClass.EXTERNAL_REVERSIBLE) is Decision.ALLOW
    assert decide(AutonomyLevel.PRODUCTION_GUARDED, ActionClass.EXTERNAL_IRREVERSIBLE) is Decision.HUMAN_GATE


# ---- failure taxonomy --------------------------------------------------- #


def test_failure_classification():
    assert classify("rg: command not found") is FailureType.MISSING_CAPABILITY
    assert classify("request timed out after 60s") is FailureType.TIMEOUT
    assert classify("spend ceiling LIMIT_REACHED") is FailureType.BUDGET_EXCEEDED
    assert classify("blocked by local-only network policy") is FailureType.SECURITY_BLOCK
    assert classify("requires macOS/Xcode") is FailureType.PLATFORM_LIMITATION
    assert classify("provider unavailable 503") is FailureType.PROVIDER_FAILURE
    assert classify("connection refused") is FailureType.ENVIRONMENT_FAILURE
    assert classify("something weird happened") is FailureType.INTERNAL_BUG


def test_recommended_actions():
    assert recommended_action(FailureType.MISSING_CAPABILITY) == "acquire_capability"
    assert recommended_action(FailureType.PLATFORM_LIMITATION) == "blocked_platform"
    assert recommended_action(FailureType.SECURITY_BLOCK) == "abort"
    assert recommended_action(FailureType.TIMEOUT) == "retry"


# ---- idempotency -------------------------------------------------------- #


def test_side_effect_runs_once():
    store = IdempotencyStore()
    op = OperationKey("m1", "deploy", "op-1")
    calls: list[int] = []

    def effect():
        calls.append(1)
        return "deployed"

    r1 = run_once(store, op, effect)
    assert r1.executed is True and r1.result == "deployed"
    r2 = run_once(store, op, effect)   # retry same operation
    assert r2.executed is False and r2.result == "deployed"
    assert len(calls) == 1             # side effect NOT duplicated


def test_raising_side_effect_is_retryable():
    store = IdempotencyStore()
    op = OperationKey("m1", "send", "op-2")
    attempts: list[int] = []

    def flaky():
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("transient")
        return "sent"

    try:
        run_once(store, op, flaky)
    except RuntimeError:
        pass
    assert not store.is_done(op)        # failure not recorded
    r = run_once(store, op, flaky)       # retry succeeds
    assert r.executed is True and r.result == "sent"


def test_snapshot_restore_survives_restart():
    store = IdempotencyStore()
    op = OperationKey("m1", "n", "op-3")
    run_once(store, op, lambda: "x")
    snap = store.snapshot()
    fresh = IdempotencyStore()
    fresh.restore(snap)
    assert fresh.is_done(op)            # dedup survives a simulated restart
