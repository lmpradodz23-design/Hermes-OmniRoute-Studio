"""Tests for the Resource Governor budget-state roll-up (agent/budget_state.py).

These exercise the pure aggregation logic AND the adapters against the REAL,
unchanged enforcer types (`IterationBudget`, `SpendCeilingConfig`, `SpendStatus`)
to prove the module reuses them rather than reimplementing budgeting.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from agent.budget_state import (
    BudgetDimension,
    BudgetState,
    aggregate,
    dimension_from_counter,
    dimension_from_iteration_budget,
    dimension_from_usd,
    dimensions_from_spend,
    snapshot_from_mapping,
    worst,
)


# --------------------------------------------------------------------------- #
# Core dimension state
# --------------------------------------------------------------------------- #


def test_untracked_dimension_is_always_within_budget():
    # No limit, or a zero/negative limit (the enforcers' "unlimited"), never
    # makes the roll-up worse — even with large usage.
    for limit in (None, 0, 0.0, -1):
        dim = BudgetDimension("x", used=10_000, limit=limit)
        assert dim.tracked is False
        assert dim.ratio is None
        assert dim.state is BudgetState.WITHIN_BUDGET


def test_below_warning_ratio_is_within_budget():
    dim = BudgetDimension("x", used=79, limit=100, warning_ratio=0.8)
    assert dim.ratio == pytest.approx(0.79)
    assert dim.state is BudgetState.WITHIN_BUDGET


def test_at_or_above_warning_ratio_is_near_limit():
    assert BudgetDimension("x", used=80, limit=100, warning_ratio=0.8).state is (
        BudgetState.NEAR_LIMIT
    )
    assert BudgetDimension("x", used=95, limit=100).state is BudgetState.NEAR_LIMIT


def test_at_or_above_limit_is_limit_reached():
    assert BudgetDimension("x", used=100, limit=100).state is BudgetState.LIMIT_REACHED
    assert BudgetDimension("x", used=150, limit=100).state is BudgetState.LIMIT_REACHED


def test_override_required_outranks_numeric_state():
    # Even with trivial usage, an override flag forces OVERRIDE_REQUIRED.
    dim = BudgetDimension("x", used=1, limit=1000, override_required=True)
    assert dim.state is BudgetState.OVERRIDE_REQUIRED


def test_floor_raises_state_but_never_lowers_it():
    # A warning floor lifts an otherwise-fine dimension to NEAR_LIMIT ...
    low = BudgetDimension("x", used=1, limit=100, floor=BudgetState.NEAR_LIMIT)
    assert low.state is BudgetState.NEAR_LIMIT
    # ... but does not *reduce* a worse numeric state.
    high = BudgetDimension("x", used=100, limit=100, floor=BudgetState.NEAR_LIMIT)
    assert high.state is BudgetState.LIMIT_REACHED


# --------------------------------------------------------------------------- #
# worst() / aggregate() roll-up
# --------------------------------------------------------------------------- #


def test_worst_ordering():
    assert worst([]) is BudgetState.WITHIN_BUDGET
    assert (
        worst([BudgetState.WITHIN_BUDGET, BudgetState.NEAR_LIMIT])
        is BudgetState.NEAR_LIMIT
    )
    assert (
        worst([BudgetState.LIMIT_REACHED, BudgetState.NEAR_LIMIT])
        is BudgetState.LIMIT_REACHED
    )
    assert (
        worst([BudgetState.LIMIT_REACHED, BudgetState.OVERRIDE_REQUIRED])
        is BudgetState.OVERRIDE_REQUIRED
    )


def test_aggregate_is_worst_state_wins_and_drops_none():
    snap = aggregate(
        [
            BudgetDimension("a", used=10, limit=100),  # within
            None,  # absent enforcer
            BudgetDimension("b", used=90, limit=100),  # near
            BudgetDimension("c", used=100, limit=100),  # reached
        ]
    )
    assert len(snap.dimensions) == 3
    assert snap.state is BudgetState.LIMIT_REACHED
    assert snap.within_budget is False
    # breaching() is most-severe-first and excludes healthy dims.
    breaching = snap.breaching()
    assert [d.name for d in breaching] == ["c", "b"]


def test_empty_snapshot_is_within_budget():
    assert aggregate([]).state is BudgetState.WITHIN_BUDGET
    assert aggregate([None, None]).within_budget is True


def test_snapshot_requires_override():
    snap = aggregate(
        [
            BudgetDimension("a", used=10, limit=100),
            BudgetDimension("b", used=1, limit=100, override_required=True),
        ]
    )
    assert snap.state is BudgetState.OVERRIDE_REQUIRED
    assert snap.requires_override is True


def test_snapshot_to_dict_shape():
    snap = aggregate([BudgetDimension("a", used=80, limit=100, unit="calls")])
    d = snap.to_dict()
    assert d["state"] == "NEAR_LIMIT"
    assert d["dimensions"][0]["name"] == "a"
    assert d["dimensions"][0]["ratio"] == pytest.approx(0.8)
    assert d["dimensions"][0]["state"] == "NEAR_LIMIT"


# --------------------------------------------------------------------------- #
# Adapters onto the REAL enforcer types (proves reuse)
# --------------------------------------------------------------------------- #


def test_adapter_reuses_real_iteration_budget():
    from agent.iteration_budget import IterationBudget

    budget = IterationBudget(max_total=10)
    for _ in range(9):
        assert budget.consume() is True
    dim = dimension_from_iteration_budget(budget)
    assert dim is not None
    assert dim.name == "tool_calls"
    assert dim.used == 9.0
    assert dim.limit == 10.0
    assert dim.state is BudgetState.NEAR_LIMIT  # 0.9 >= 0.8

    assert budget.consume() is True  # 10/10
    assert dimension_from_iteration_budget(budget).state is BudgetState.LIMIT_REACHED
    assert budget.consume() is False  # enforcer still hard-stops
    assert dimension_from_iteration_budget(None) is None


def test_adapter_reuses_real_spend_ceiling_types():
    from agent.spend_ceiling import SpendCeilingConfig, SpendStatus

    config = SpendCeilingConfig.from_mapping(
        {"session_usd": "10", "daily_usd": "100", "warning_ratio": "0.8"}
    )
    # Session near limit (9/10), daily healthy (9/100), no warning string.
    status = SpendStatus(
        session_spend_usd=Decimal("9"),
        daily_spend_usd=Decimal("9"),
        warning=None,
    )
    dims = dimensions_from_spend(status, config)
    by_name = {d.name: d for d in dims}
    assert by_name["spend_session_usd"].state is BudgetState.NEAR_LIMIT
    assert by_name["spend_daily_usd"].state is BudgetState.WITHIN_BUDGET
    assert aggregate(dims).state is BudgetState.NEAR_LIMIT


def test_spend_warning_string_floors_dimensions_to_near_limit():
    from agent.spend_ceiling import SpendCeilingConfig, SpendStatus

    config = SpendCeilingConfig.from_mapping({"session_usd": "10", "daily_usd": "100"})
    # Numerically low, but the enforcer emitted a warning -> floor to NEAR_LIMIT.
    status = SpendStatus(
        session_spend_usd=Decimal("1"),
        daily_spend_usd=Decimal("1"),
        warning="approaching session ceiling",
    )
    dims = dimensions_from_spend(status, config)
    assert all(d.state is BudgetState.NEAR_LIMIT for d in dims)


def test_spend_zero_limits_stay_untracked():
    from agent.spend_ceiling import SpendCeilingConfig, SpendStatus

    # Disabled ceiling (both limits 0) -> both dims untracked/within budget.
    config = SpendCeilingConfig.from_mapping({})
    status = SpendStatus(
        session_spend_usd=Decimal("500"),
        daily_spend_usd=Decimal("500"),
        warning=None,
    )
    dims = dimensions_from_spend(status, config)
    assert all(d.tracked is False for d in dims)
    assert aggregate(dims).within_budget is True


def test_dimension_from_usd_confirmation_requires_override():
    dim = dimension_from_usd("mission_cost", "2.50", "5.00", requires_confirmation=True)
    assert dim.state is BudgetState.OVERRIDE_REQUIRED


def test_snapshot_from_mapping():
    snap = snapshot_from_mapping(
        {
            "tokens": {"used": 40_000, "limit": 50_000, "unit": "tok"},  # near
            "wall_seconds": {"used": 10, "limit": 3600, "unit": "s"},  # within
            "parallel_agents": {"used": 8, "limit": 8},  # reached
        }
    )
    assert snap.state is BudgetState.LIMIT_REACHED
    assert {d.name for d in snap.breaching()} == {"parallel_agents", "tokens"}
