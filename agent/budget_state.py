"""Resource Governor — a unified, read-only budget-state roll-up.

The Autonomy Kernel needs a single answer to "how close is this mission to any
of its limits?" so a watchdog/planner can slow down, ask for confirmation, or
stop. Today that signal is spread across several *already-enforced* subsystems,
each of which owns its own hard enforcement and is independently tested:

  - USD cost      -> ``agent.spend_ceiling.SpendCeilingPolicy`` (``SpendStatus``)
  - tool calls    -> ``agent.iteration_budget.IterationBudget``
  - credits/API   -> ``agent.credits_tracker``
  - wall time     -> kanban ``max_runtime_seconds``
  - parallel work -> auxiliary-client concurrency semaphores

This module does **not** enforce anything and does **not** replace those
enforcers. It is a pure, side-effect-free aggregator that maps each enforcer's
current reading onto one shared ``BudgetState`` enum and rolls them up
worst-state-wins, so the mission layer has a single ``WITHIN_BUDGET /
NEAR_LIMIT / LIMIT_REACHED / OVERRIDE_REQUIRED`` signal to act on.

Design notes:
  - stdlib only; imports none of the enforcers, so it stays trivially testable
    and cannot perturb their enforcement paths. Adapters accept duck-typed
    objects (whatever exposes the needed attributes).
  - an untracked dimension (no limit, or a limit of 0 which every enforcer here
    treats as "unlimited") never makes the roll-up worse — absence of a ceiling
    is not a breach.
  - ``OVERRIDE_REQUIRED`` is the gating state: an action can only proceed with
    explicit human authorization (mirrors ``SpendDecision.requires_confirmation``
    at the confirmation threshold). It outranks ``LIMIT_REACHED``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping


class BudgetState(str, Enum):
    """Shared budget signal (see module docstring). Ordered by severity."""

    WITHIN_BUDGET = "WITHIN_BUDGET"
    NEAR_LIMIT = "NEAR_LIMIT"
    LIMIT_REACHED = "LIMIT_REACHED"
    OVERRIDE_REQUIRED = "OVERRIDE_REQUIRED"


# Severity ranking for worst-state-wins roll-up.
_SEVERITY: dict[BudgetState, int] = {
    BudgetState.WITHIN_BUDGET: 0,
    BudgetState.NEAR_LIMIT: 1,
    BudgetState.LIMIT_REACHED: 2,
    BudgetState.OVERRIDE_REQUIRED: 3,
}

DEFAULT_WARNING_RATIO = 0.8


def _as_float(value: Any) -> float | None:
    """Best-effort float coercion (accepts int/float/Decimal/str). ``None`` on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def worst(states: Iterable[BudgetState]) -> BudgetState:
    """Return the most severe state in ``states`` (``WITHIN_BUDGET`` if empty)."""
    result = BudgetState.WITHIN_BUDGET
    for state in states:
        if _SEVERITY[state] > _SEVERITY[result]:
            result = state
    return result


@dataclass(frozen=True)
class BudgetDimension:
    """One budgeted resource's current reading.

    ``limit`` of ``None`` or ``<= 0`` means "untracked/unlimited" — such a
    dimension is always ``WITHIN_BUDGET`` regardless of ``used``. Set
    ``override_required`` when the underlying enforcer says the next action
    needs explicit human authorization (e.g. spend past a confirmation
    threshold); that forces ``OVERRIDE_REQUIRED``.
    """

    name: str
    used: float = 0.0
    limit: float | None = None
    warning_ratio: float = DEFAULT_WARNING_RATIO
    override_required: bool = False
    unit: str = ""
    # An enforcer may already know the state is at least this severe (e.g. it
    # emitted a warning string) even if the numeric ratio disagrees. The final
    # state is never *less* severe than this floor.
    floor: BudgetState = BudgetState.WITHIN_BUDGET

    @property
    def tracked(self) -> bool:
        return self.limit is not None and self.limit > 0

    @property
    def ratio(self) -> float | None:
        """Fraction of the limit used (``None`` when untracked)."""
        if not self.tracked:
            return None
        assert self.limit is not None  # for type-checkers; guarded by ``tracked``
        return max(0.0, self.used) / self.limit

    @property
    def state(self) -> BudgetState:
        if self.override_required:
            return BudgetState.OVERRIDE_REQUIRED
        numeric = BudgetState.WITHIN_BUDGET
        ratio = self.ratio
        if ratio is not None:
            if ratio >= 1.0:
                numeric = BudgetState.LIMIT_REACHED
            elif ratio >= self.warning_ratio:
                numeric = BudgetState.NEAR_LIMIT
        return worst((numeric, self.floor))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "used": self.used,
            "limit": self.limit,
            "unit": self.unit,
            "ratio": self.ratio,
            "state": self.state.value,
        }


@dataclass(frozen=True)
class BudgetSnapshot:
    """A roll-up of every budgeted dimension for a mission/session."""

    dimensions: tuple[BudgetDimension, ...] = ()

    @property
    def state(self) -> BudgetState:
        return worst(dim.state for dim in self.dimensions)

    @property
    def within_budget(self) -> bool:
        return self.state == BudgetState.WITHIN_BUDGET

    @property
    def requires_override(self) -> bool:
        return self.state == BudgetState.OVERRIDE_REQUIRED

    def breaching(self) -> tuple[BudgetDimension, ...]:
        """Dimensions that are NEAR_LIMIT or worse, most-severe first."""
        flagged = [d for d in self.dimensions if d.state != BudgetState.WITHIN_BUDGET]
        flagged.sort(key=lambda d: _SEVERITY[d.state], reverse=True)
        return tuple(flagged)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "dimensions": [d.to_dict() for d in self.dimensions],
        }


def aggregate(dimensions: Iterable[BudgetDimension | None]) -> BudgetSnapshot:
    """Build a snapshot, silently dropping ``None`` dimensions (absent enforcers)."""
    return BudgetSnapshot(tuple(d for d in dimensions if d is not None))


# --------------------------------------------------------------------------- #
# Adapters onto the existing (unchanged) enforcers. Duck-typed on purpose so
# this module imports none of them and can be unit-tested in isolation.
# --------------------------------------------------------------------------- #


def dimension_from_iteration_budget(
    budget: Any,
    *,
    name: str = "tool_calls",
    warning_ratio: float = DEFAULT_WARNING_RATIO,
) -> BudgetDimension | None:
    """Adapt an ``agent.iteration_budget.IterationBudget`` (``used``/``max_total``)."""
    if budget is None:
        return None
    used = _as_float(getattr(budget, "used", None))
    limit = _as_float(getattr(budget, "max_total", None))
    if used is None:
        return None
    return BudgetDimension(
        name=name, used=used, limit=limit, warning_ratio=warning_ratio, unit="calls"
    )


def dimensions_from_spend(
    status: Any,
    config: Any,
    *,
    warning_ratio: float | None = None,
) -> list[BudgetDimension]:
    """Adapt a ``SpendStatus`` + ``SpendCeilingConfig`` into session/daily USD dims.

    ``config`` is duck-typed on ``session_usd`` / ``daily_usd`` /
    ``warning_ratio``; a limit of 0 (the enforcer's "unlimited") stays untracked.
    If ``status.warning`` is set the enforcer already decided things are at least
    NEAR_LIMIT, so both USD dimensions are floored to NEAR_LIMIT.
    """
    if status is None or config is None:
        return []
    ratio = warning_ratio
    if ratio is None:
        ratio = _as_float(getattr(config, "warning_ratio", None)) or DEFAULT_WARNING_RATIO
    floor = (
        BudgetState.NEAR_LIMIT
        if getattr(status, "warning", None)
        else BudgetState.WITHIN_BUDGET
    )
    dims: list[BudgetDimension] = []
    for name, used_attr, limit_attr in (
        ("spend_session_usd", "session_spend_usd", "session_usd"),
        ("spend_daily_usd", "daily_spend_usd", "daily_usd"),
    ):
        used = _as_float(getattr(status, used_attr, None)) or 0.0
        limit = _as_float(getattr(config, limit_attr, None))
        dims.append(
            BudgetDimension(
                name=name,
                used=used,
                limit=limit,
                warning_ratio=ratio,
                unit="usd",
                floor=floor,
            )
        )
    return dims


def dimension_from_usd(
    name: str,
    spent: Any,
    limit: Any,
    *,
    warning_ratio: float = DEFAULT_WARNING_RATIO,
    requires_confirmation: bool = False,
) -> BudgetDimension:
    """Generic USD dimension (e.g. a per-mission cost budget)."""
    return BudgetDimension(
        name=name,
        used=_as_float(spent) or 0.0,
        limit=_as_float(limit),
        warning_ratio=warning_ratio,
        override_required=bool(requires_confirmation),
        unit="usd",
    )


def dimension_from_counter(
    name: str,
    used: Any,
    limit: Any,
    *,
    warning_ratio: float = DEFAULT_WARNING_RATIO,
    unit: str = "",
) -> BudgetDimension:
    """Generic count/time dimension (parallel agents, wall-seconds, tokens...)."""
    return BudgetDimension(
        name=name,
        used=_as_float(used) or 0.0,
        limit=_as_float(limit),
        warning_ratio=warning_ratio,
        unit=unit,
    )


def snapshot_from_mapping(readings: Mapping[str, Mapping[str, Any]]) -> BudgetSnapshot:
    """Build a snapshot from a plain ``{name: {used, limit, unit?, warning_ratio?}}`` map.

    Convenience for callers/tests that already have numeric readings and don't
    want to hold references to the live enforcer objects.
    """
    dims: list[BudgetDimension] = []
    for name, reading in readings.items():
        dims.append(
            dimension_from_counter(
                name,
                reading.get("used"),
                reading.get("limit"),
                warning_ratio=float(
                    reading.get("warning_ratio", DEFAULT_WARNING_RATIO)
                ),
                unit=str(reading.get("unit", "")),
            )
        )
    return aggregate(dims)


__all__ = [
    "BudgetState",
    "BudgetDimension",
    "BudgetSnapshot",
    "DEFAULT_WARNING_RATIO",
    "worst",
    "aggregate",
    "dimension_from_iteration_budget",
    "dimensions_from_spend",
    "dimension_from_usd",
    "dimension_from_counter",
    "snapshot_from_mapping",
]
