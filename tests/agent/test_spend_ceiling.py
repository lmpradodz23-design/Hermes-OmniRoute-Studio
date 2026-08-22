from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest


def _api():
    from agent.spend_ceiling import (
        SpendCeilingBlocked,
        SpendCeilingConfig,
        SpendCeilingPolicy,
    )

    return SpendCeilingBlocked, SpendCeilingConfig, SpendCeilingPolicy


def test_default_config_exposes_disabled_user_owned_spend_controls() -> None:
    from hermes_cli.config import DEFAULT_CONFIG

    assert DEFAULT_CONFIG["security"]["spend_ceiling"] == {
        "session_usd": "0",
        "daily_usd": "0",
        "warning_ratio": "0.80",
        "confirmation_threshold_usd": "0",
    }


def test_preflight_estimate_uses_real_pricing_and_maximum_output_tokens() -> None:
    from agent.spend_ceiling import estimate_request_spend

    estimated = estimate_request_spend(
        model="gpt-5.6-luna",
        provider="openai",
        base_url="https://api.openai.com/v1",
        api_key="",
        input_tokens=1_000_000,
        max_output_tokens=1_000_000,
    )

    assert estimated == Decimal("7.00")


def test_expensive_request_confirmation_is_human_only_and_fail_closed() -> None:
    from agent.spend_ceiling import request_spend_confirmation

    assert request_spend_confirmation(None, Decimal("1.25")) is False
    assert (
        request_spend_confirmation(
            lambda question, choices: choices[0], Decimal("1.25")
        )
        is True
    )
    assert (
        request_spend_confirmation(
            lambda question, choices: "Negar", Decimal("1.25")
        )
        is False
    )


def _clock() -> datetime:
    return datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def _policy(tmp_path, *, session="1.00", daily="10.00", confirm="0.00"):
    _, SpendCeilingConfig, SpendCeilingPolicy = _api()
    config = SpendCeilingConfig.from_mapping(
        {
            "session_usd": session,
            "daily_usd": daily,
            "warning_ratio": "0.80",
            "confirmation_threshold_usd": confirm,
        }
    )
    return SpendCeilingPolicy(config, tmp_path / "spend-ledger.sqlite3", clock=_clock)


def test_actual_cost_crosses_warning_then_blocks_the_next_request(tmp_path) -> None:
    SpendCeilingBlocked, _, _ = _api()
    policy = _policy(tmp_path)

    first = policy.authorize(
        session_id="session-a",
        task_id="task-a",
        request_id="request-1",
        estimated_cost_usd=Decimal("0.10"),
    )
    assert first.allowed is True
    assert first.warning is None

    settled = policy.settle(request_id="request-1", actual_cost_usd=Decimal("1.01"))
    assert settled.session_spend_usd == Decimal("1.01")
    assert settled.warning is not None
    assert "100%" in settled.warning

    with pytest.raises(SpendCeilingBlocked, match=r"^BLOCKED:.*session spend ceiling"):
        policy.authorize(
            session_id="session-a",
            task_id="task-a",
            request_id="request-2",
            estimated_cost_usd=Decimal("0.01"),
        )


def test_daily_ceiling_is_shared_across_sessions(tmp_path) -> None:
    SpendCeilingBlocked, _, _ = _api()
    policy = _policy(tmp_path, session="5.00", daily="1.00")

    policy.authorize(
        session_id="session-a",
        task_id="task-a",
        request_id="request-a",
        estimated_cost_usd=Decimal("0.10"),
    )
    policy.settle(request_id="request-a", actual_cost_usd=Decimal("0.60"))
    policy.authorize(
        session_id="session-b",
        task_id="task-b",
        request_id="request-b",
        estimated_cost_usd=Decimal("0.10"),
    )
    policy.settle(request_id="request-b", actual_cost_usd=Decimal("0.45"))

    with pytest.raises(SpendCeilingBlocked, match=r"^BLOCKED:.*daily spend ceiling"):
        policy.authorize(
            session_id="session-c",
            task_id="task-c",
            request_id="request-c",
            estimated_cost_usd=Decimal("0.01"),
        )


def test_estimate_requires_confirmation_above_threshold_without_reserving(tmp_path) -> None:
    policy = _policy(tmp_path, session="5.00", daily="10.00", confirm="0.25")

    pending = policy.authorize(
        session_id="session-a",
        task_id="task-a",
        request_id="request-1",
        estimated_cost_usd=Decimal("0.30"),
        confirmed=False,
    )
    assert pending.allowed is False
    assert pending.requires_confirmation is True
    assert pending.estimated_cost_usd == Decimal("0.30")
    assert policy.status("session-a").session_spend_usd == Decimal("0.00")

    approved = policy.authorize(
        session_id="session-a",
        task_id="task-a",
        request_id="request-1",
        estimated_cost_usd=Decimal("0.30"),
        confirmed=True,
    )
    assert approved.allowed is True
    assert approved.requires_confirmation is False
    assert policy.status("session-a").session_spend_usd == Decimal("0.30")


def test_external_budget_tool_cannot_change_the_effective_local_ceiling(tmp_path) -> None:
    SpendCeilingBlocked, _, _ = _api()
    policy = _policy(tmp_path, session="0.50", daily="5.00")
    external_omniroute_budget = {"session_usd": Decimal("0.50")}

    policy.authorize(
        session_id="session-a",
        task_id="task-a",
        request_id="request-1",
        estimated_cost_usd=Decimal("0.10"),
    )
    policy.settle(request_id="request-1", actual_cost_usd=Decimal("0.51"))

    external_omniroute_budget["session_usd"] = Decimal("999.00")
    assert external_omniroute_budget["session_usd"] == Decimal("999.00")

    with pytest.raises(SpendCeilingBlocked, match=r"^BLOCKED:"):
        policy.authorize(
            session_id="session-a",
            task_id="task-a",
            request_id="request-2",
            estimated_cost_usd=Decimal("0.01"),
        )


def test_duplicate_settlement_is_idempotent(tmp_path) -> None:
    policy = _policy(tmp_path)
    policy.authorize(
        session_id="session-a",
        task_id="task-a",
        request_id="request-1",
        estimated_cost_usd=Decimal("0.10"),
    )

    first = policy.settle(request_id="request-1", actual_cost_usd=Decimal("0.20"))
    second = policy.settle(request_id="request-1", actual_cost_usd=Decimal("0.20"))

    assert first.session_spend_usd == Decimal("0.20")
    assert second.session_spend_usd == Decimal("0.20")


def test_retry_with_a_more_expensive_route_rechecks_the_hard_ceiling(tmp_path) -> None:
    SpendCeilingBlocked, _, _ = _api()
    policy = _policy(tmp_path, session="0.50")
    policy.authorize(
        session_id="session-a",
        task_id="task-a",
        request_id="request-1",
        estimated_cost_usd=Decimal("0.10"),
    )

    with pytest.raises(SpendCeilingBlocked, match="session spend ceiling"):
        policy.authorize(
            session_id="session-a",
            task_id="task-a",
            request_id="request-1",
            estimated_cost_usd=Decimal("0.60"),
        )


def test_retry_crossing_confirmation_threshold_still_requires_the_owner(tmp_path) -> None:
    policy = _policy(tmp_path, session="5.00", confirm="0.25")
    policy.authorize(
        session_id="session-a",
        task_id="task-a",
        request_id="request-1",
        estimated_cost_usd=Decimal("0.10"),
    )

    pending = policy.authorize(
        session_id="session-a",
        task_id="task-a",
        request_id="request-1",
        estimated_cost_usd=Decimal("0.30"),
    )
    assert pending.allowed is False
    assert pending.requires_confirmation is True

    approved = policy.authorize(
        session_id="session-a",
        task_id="task-a",
        request_id="request-1",
        estimated_cost_usd=Decimal("0.30"),
        confirmed=True,
    )
    assert approved.allowed is True
    assert policy.status("session-a").session_spend_usd == Decimal("0.30")


@pytest.mark.parametrize(
    ("mapping", "message"),
    [
        ({"session_usd": -1}, "session_usd"),
        ({"daily_usd": True}, "daily_usd"),
        ({"warning_ratio": 1.1}, "warning_ratio"),
        ({"confirmation_threshold_usd": "not-money"}, "confirmation_threshold_usd"),
    ],
)
def test_invalid_security_config_is_rejected(mapping, message) -> None:
    _, SpendCeilingConfig, _ = _api()

    with pytest.raises(ValueError, match=message):
        SpendCeilingConfig.from_mapping(mapping)
