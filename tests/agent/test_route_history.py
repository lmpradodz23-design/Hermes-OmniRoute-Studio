"""Tests for learned routing (agent/route_history.py)."""

from __future__ import annotations

from agent.route_history import (
    Candidate,
    RouteHistory,
    RouteRecord,
    is_eligible,
    select,
)


def _hist(records) -> RouteHistory:
    return RouteHistory(records)


def _good_records(task, model, provider, n=5):
    return [
        RouteRecord(task, model, provider, success=True, verification_score=0.95,
                    latency_ms=100, cost_usd=0.01)
        for _ in range(n)
    ]


def test_eligibility_gate_blocks_remote_under_local_only():
    remote = Candidate("gpt-x", "openai", is_local=False)
    local = Candidate("llama", "ollama", is_local=True)
    assert is_eligible(remote, local_only=False) is True
    assert is_eligible(remote, local_only=True) is False   # absolute precedence
    assert is_eligible(local, local_only=True) is True


def test_local_only_beats_high_history_remote():
    # remote model has a great track record, local has none.
    hist = _hist(_good_records("code", "gpt-x", "openai", n=10))
    candidates = [
        Candidate("gpt-x", "openai", is_local=False),   # remote, great history
        Candidate("llama", "ollama", is_local=True),    # local, no history
    ]
    decision = select(candidates, hist, task_type="code", local_only=True)
    assert decision.model == "llama"   # privacy wins over history
    assert decision.provider == "ollama"
    assert decision.eligible_count == 1


def test_capability_and_availability_gate():
    assert not is_eligible(
        Candidate("m", "p", is_local=True, capability_ok=False), local_only=False
    )
    assert not is_eligible(
        Candidate("m", "p", is_local=True, available=False), local_only=False
    )


def test_history_selects_better_model_when_both_eligible():
    hist = _hist(
        _good_records("code", "strong", "p", n=5)
        + [
            RouteRecord("code", "weak", "p", success=False, verification_score=0.2,
                        latency_ms=100, cost_usd=0.01)
            for _ in range(5)
        ]
    )
    candidates = [
        Candidate("strong", "p", is_local=True),
        Candidate("weak", "p", is_local=True),
    ]
    decision = select(candidates, hist, task_type="code", local_only=False)
    assert decision.model == "strong"


def test_unbenchmarked_model_is_not_starved():
    # 'known' has only mediocre history; 'fresh' has none -> fresh gets a neutral
    # prior and can win, so exploration is possible (history doesn't solely rule).
    hist = _hist(
        [
            RouteRecord("code", "known", "p", success=True, verification_score=0.5,
                        latency_ms=100, cost_usd=0.01)
            for _ in range(5)
        ]
    )
    candidates = [
        Candidate("known", "p", is_local=True),
        Candidate("fresh", "p", is_local=True),
    ]
    decision = select(candidates, hist, task_type="code", local_only=False)
    # fresh (prior 0.6) should out-score known (0.5) -> not starved
    assert decision.model == "fresh"


def test_no_eligible_candidate():
    candidates = [Candidate("gpt-x", "openai", is_local=False)]
    decision = select(candidates, _hist([]), task_type="code", local_only=True)
    assert decision.model is None
    assert decision.eligible_count == 0
    assert decision.reason == "no_eligible_candidate"


def test_stats_aggregation():
    hist = _hist(_good_records("code", "m", "p", n=4))
    st = hist.stats("code", "m")
    assert st.n == 4
    assert st.success_rate == 1.0
    assert st.mean_score == 0.95
    assert hist.stats("code", "absent").n == 0
