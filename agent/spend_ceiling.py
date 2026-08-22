"""Router-independent spend ceilings enforced by the Hermes core.

The policy intentionally lives outside tools and provider plugins.  A model can
request that OmniRoute changes its own budget, but it cannot mutate the local
policy snapshot held by the running agent.
"""

from __future__ import annotations

import math
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping


_ZERO = Decimal("0")


class SpendCeilingBlocked(RuntimeError):
    """Raised before a provider request that would violate a hard ceiling."""


def _decimal_setting(name: str, value: Any, default: str) -> Decimal:
    if value is None:
        value = default
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a non-negative decimal")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be a non-negative decimal") from exc
    if not parsed.is_finite() or parsed < _ZERO:
        raise ValueError(f"{name} must be a non-negative finite decimal")
    return parsed


@dataclass(frozen=True)
class SpendCeilingConfig:
    """A validated, immutable snapshot of user-controlled spend limits."""

    session_usd: Decimal = _ZERO
    daily_usd: Decimal = _ZERO
    warning_ratio: Decimal = Decimal("0.80")
    confirmation_threshold_usd: Decimal = _ZERO

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None) -> "SpendCeilingConfig":
        source = values or {}
        warning_ratio = _decimal_setting(
            "warning_ratio", source.get("warning_ratio"), "0.80"
        )
        if warning_ratio <= _ZERO or warning_ratio > Decimal("1"):
            raise ValueError("warning_ratio must be greater than 0 and at most 1")
        return cls(
            session_usd=_decimal_setting(
                "session_usd", source.get("session_usd"), "0"
            ),
            daily_usd=_decimal_setting("daily_usd", source.get("daily_usd"), "0"),
            warning_ratio=warning_ratio,
            confirmation_threshold_usd=_decimal_setting(
                "confirmation_threshold_usd",
                source.get("confirmation_threshold_usd"),
                "0",
            ),
        )

    @property
    def enabled(self) -> bool:
        return self.session_usd > _ZERO or self.daily_usd > _ZERO


@dataclass(frozen=True)
class SpendDecision:
    allowed: bool
    requires_confirmation: bool
    estimated_cost_usd: Decimal
    warning: str | None = None


@dataclass(frozen=True)
class SpendStatus:
    session_spend_usd: Decimal
    daily_spend_usd: Decimal
    warning: str | None


class SpendCeilingPolicy:
    """Persistent, concurrency-safe authorization and settlement ledger."""

    def __init__(
        self,
        config: SpendCeilingConfig,
        ledger_path: str | Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.config = config
        self.ledger_path = Path(ledger_path)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        if self.config.enabled:
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS spend_requests (
                    request_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    spend_day TEXT NOT NULL,
                    estimated_usd TEXT NOT NULL,
                    actual_usd TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_spend_requests_session
                    ON spend_requests(session_id);
                CREATE INDEX IF NOT EXISTS idx_spend_requests_day
                    ON spend_requests(spend_day);
                CREATE TABLE IF NOT EXISTS spend_confirmations (
                    session_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    confirmed_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, task_id)
                );
                """
            )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.ledger_path, timeout=10)
        try:
            connection.execute("PRAGMA busy_timeout = 10000")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @staticmethod
    def _row_cost(row: tuple[str, str | None]) -> Decimal:
        estimated, actual = row
        return Decimal(actual if actual is not None else estimated)

    def _totals(
        self, connection: sqlite3.Connection, session_id: str, spend_day: str
    ) -> tuple[Decimal, Decimal]:
        session_rows = connection.execute(
            "SELECT estimated_usd, actual_usd FROM spend_requests WHERE session_id = ?",
            (session_id,),
        ).fetchall()
        daily_rows = connection.execute(
            "SELECT estimated_usd, actual_usd FROM spend_requests WHERE spend_day = ?",
            (spend_day,),
        ).fetchall()
        return (
            sum((self._row_cost(row) for row in session_rows), _ZERO),
            sum((self._row_cost(row) for row in daily_rows), _ZERO),
        )

    def _warning(
        self, session_spend: Decimal, daily_spend: Decimal
    ) -> str | None:
        candidates: list[tuple[str, Decimal, Decimal]] = []
        if self.config.session_usd > _ZERO:
            candidates.append(
                ("session", session_spend / self.config.session_usd, session_spend)
            )
        if self.config.daily_usd > _ZERO:
            candidates.append(("daily", daily_spend / self.config.daily_usd, daily_spend))
        if not candidates:
            return None
        scope, ratio, amount = max(candidates, key=lambda item: item[1])
        if ratio < self.config.warning_ratio:
            return None
        percent = int(ratio * 100)
        display_percent = "100%+" if percent >= 100 else f"{percent}%"
        ceiling = (
            self.config.session_usd if scope == "session" else self.config.daily_usd
        )
        return (
            f"Spend ceiling warning: {display_percent} of the {scope} limit "
            f"(${amount} / ${ceiling})."
        )

    def _assert_within_ceiling(
        self,
        *,
        session_spend: Decimal,
        daily_spend: Decimal,
        estimate: Decimal,
    ) -> None:
        if (
            self.config.session_usd > _ZERO
            and session_spend + estimate > self.config.session_usd
        ):
            raise SpendCeilingBlocked(
                "BLOCKED: session spend ceiling would be exceeded by this request"
            )
        if (
            self.config.daily_usd > _ZERO
            and daily_spend + estimate > self.config.daily_usd
        ):
            raise SpendCeilingBlocked(
                "BLOCKED: daily spend ceiling would be exceeded by this request"
            )

    def authorize(
        self,
        *,
        session_id: str,
        task_id: str,
        request_id: str,
        estimated_cost_usd: Decimal | str | int | float,
        confirmed: bool = False,
    ) -> SpendDecision:
        estimate = _decimal_setting("estimated_cost_usd", estimated_cost_usd, "0")
        if not self.config.enabled:
            return SpendDecision(True, False, estimate, None)
        if not session_id or not task_id or not request_id:
            raise ValueError("session_id, task_id, and request_id are required")
        now = self._now()
        spend_day = now.date().isoformat()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT session_id, task_id, estimated_usd, actual_usd
                FROM spend_requests WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()
            if existing is not None:
                existing_session, existing_task, existing_estimate, actual = existing
                if existing_session != session_id or existing_task != task_id:
                    raise ValueError("request_id is already owned by another task")
                previous = Decimal(existing_estimate)
                if actual is not None or estimate <= previous:
                    status = self._status(connection, session_id, spend_day)
                    return SpendDecision(True, False, previous, status.warning)

                session_spend, daily_spend = self._totals(
                    connection, session_id, spend_day
                )
                increase = estimate - previous
                self._assert_within_ceiling(
                    session_spend=session_spend,
                    daily_spend=daily_spend,
                    estimate=increase,
                )
                confirmation_exists = connection.execute(
                    """
                    SELECT 1 FROM spend_confirmations
                    WHERE session_id = ? AND task_id = ?
                    """,
                    (session_id, task_id),
                ).fetchone()
                needs_confirmation = (
                    self.config.confirmation_threshold_usd > _ZERO
                    and estimate > self.config.confirmation_threshold_usd
                    and confirmation_exists is None
                )
                if needs_confirmation and not confirmed:
                    return SpendDecision(False, True, estimate, None)
                if needs_confirmation:
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO spend_confirmations
                            (session_id, task_id, confirmed_at)
                        VALUES (?, ?, ?)
                        """,
                        (session_id, task_id, now.isoformat()),
                    )
                connection.execute(
                    """
                    UPDATE spend_requests SET estimated_usd = ?
                    WHERE request_id = ? AND actual_usd IS NULL
                    """,
                    (str(estimate), request_id),
                )
                return SpendDecision(
                    True,
                    False,
                    estimate,
                    self._warning(
                        session_spend + increase, daily_spend + increase
                    ),
                )

            session_spend, daily_spend = self._totals(
                connection, session_id, spend_day
            )
            self._assert_within_ceiling(
                session_spend=session_spend,
                daily_spend=daily_spend,
                estimate=estimate,
            )

            confirmation_exists = connection.execute(
                """
                SELECT 1 FROM spend_confirmations
                WHERE session_id = ? AND task_id = ?
                """,
                (session_id, task_id),
            ).fetchone()
            needs_confirmation = (
                self.config.confirmation_threshold_usd > _ZERO
                and estimate > self.config.confirmation_threshold_usd
                and confirmation_exists is None
            )
            if needs_confirmation and not confirmed:
                return SpendDecision(False, True, estimate, None)
            if needs_confirmation:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO spend_confirmations
                        (session_id, task_id, confirmed_at)
                    VALUES (?, ?, ?)
                    """,
                    (session_id, task_id, now.isoformat()),
                )

            connection.execute(
                """
                INSERT INTO spend_requests
                    (request_id, session_id, task_id, spend_day,
                     estimated_usd, actual_usd, created_at)
                VALUES (?, ?, ?, ?, ?, NULL, ?)
                """,
                (
                    request_id,
                    session_id,
                    task_id,
                    spend_day,
                    str(estimate),
                    now.isoformat(),
                ),
            )
            warning = self._warning(
                session_spend + estimate, daily_spend + estimate
            )
            return SpendDecision(True, False, estimate, warning)

    def settle(
        self,
        *,
        request_id: str,
        actual_cost_usd: Decimal | str | int | float,
    ) -> SpendStatus:
        actual = _decimal_setting("actual_cost_usd", actual_cost_usd, "0")
        if not self.config.enabled:
            return SpendStatus(_ZERO, _ZERO, None)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT session_id, spend_day, actual_usd
                FROM spend_requests WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"unknown spend request: {request_id}")
            session_id, spend_day, previous_actual = row
            if previous_actual is None:
                connection.execute(
                    "UPDATE spend_requests SET actual_usd = ? WHERE request_id = ?",
                    (str(actual), request_id),
                )
            elif Decimal(previous_actual) != actual:
                raise ValueError(
                    f"spend request {request_id} was already settled with a different cost"
                )
            return self._status(connection, session_id, spend_day)

    def _status(
        self, connection: sqlite3.Connection, session_id: str, spend_day: str
    ) -> SpendStatus:
        session_spend, daily_spend = self._totals(
            connection, session_id, spend_day
        )
        return SpendStatus(
            session_spend_usd=session_spend,
            daily_spend_usd=daily_spend,
            warning=self._warning(session_spend, daily_spend),
        )

    def status(self, session_id: str) -> SpendStatus:
        if not self.config.enabled:
            return SpendStatus(_ZERO, _ZERO, None)
        with self._connection() as connection:
            return self._status(connection, session_id, self._now().date().isoformat())


def estimate_request_spend(
    *,
    model: str,
    provider: str | None,
    base_url: str | None,
    api_key: str | None,
    input_tokens: int,
    max_output_tokens: int,
) -> Decimal | None:
    """Return the worst-case provider price for a request before it is sent.

    ``None`` means the active route has no trustworthy pricing data. Callers
    with an enabled hard ceiling must fail closed in that case; guessing a zero
    price would make the ceiling cosmetic.
    """
    from agent.usage_pricing import CanonicalUsage, estimate_usage_cost

    usage = CanonicalUsage(
        input_tokens=max(0, int(input_tokens)),
        output_tokens=max(0, int(max_output_tokens)),
    )
    result = estimate_usage_cost(
        model,
        usage,
        provider=provider,
        base_url=base_url,
        api_key=api_key or "",
    )
    return result.amount_usd


def request_spend_confirmation(
    callback: Callable[..., Any] | None, estimated_cost_usd: Decimal
) -> bool:
    """Ask the owner to approve one expensive task; silence always denies.

    This deliberately calls the platform's human-input transport directly.
    It does not consult approvals.mode, YOLO, a model verdict, or a remembered
    tool approval, so only an actual response from the owner can authorize it.
    """
    if callback is None:
        return False
    try:
        import json

        from tools.clarify_tool import clarify_tool

        payload = json.loads(
            clarify_tool(
                question=(
                    "Esta tarefa pode custar até "
                    f"US$ {estimated_cost_usd}. Autorizar esta tarefa?"
                ),
                choices=["Autorizar uma vez", "Negar"],
                callback=callback,
            )
        )
        response = str(payload.get("user_response") or "").strip().casefold()
        return response == "autorizar uma vez"
    except Exception:
        return False
