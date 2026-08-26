"""Safe transactional repair (Wave 5/6, §55).

Generalizes the textbook envelope already proven in
hermes_state.repair_state_db_schema (backup -> escalate -> verify -> attempt-cap,
never wipe) into a reusable, minimal-component repair transaction:

  DIAGNOSE -> CHECKPOINT -> BACKUP(when needed) -> PLAN -> REPAIR -> VERIFY
             -> (ok) COMMIT | (fail) ROLLBACK -> VERIFY ROLLBACK -> REPORT

Never uses delete-everything / wipe-config / delete-state.db / reinstall as a
first response — repairs the smallest component. Pure orchestration with injected
callables; every step yields evidence. Adds the BLOCKED health status doctor lacks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class Health(str, Enum):
    OK = "OK"
    WARN = "WARN"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"     # platform/external gated (doctor lacked this)


class RepairOutcome(str, Enum):
    REPAIRED = "REPAIRED"
    ROLLED_BACK = "ROLLED_BACK"      # repair failed, safely reverted
    ROLLBACK_FAILED = "ROLLBACK_FAILED"
    BLOCKED = "BLOCKED"
    NOT_NEEDED = "NOT_NEEDED"


@dataclass(frozen=True)
class RepairPlan:
    """Injected steps for one component's repair. Each returns True on success."""

    component: str
    diagnose: Callable[[], Health]           # current health
    repair: Callable[[], bool]               # apply the minimal fix
    verify: Callable[[], bool]               # confirm health after repair
    rollback: Callable[[], bool] = lambda: True   # revert on failure
    backup: Callable[[], bool] | None = None      # take a backup first (when needed)
    max_attempts: int = 2                    # attempt cap — no infinite repair


@dataclass(frozen=True)
class RepairResult:
    component: str
    outcome: RepairOutcome
    attempts: int
    evidence: tuple[str, ...] = ()


def run_repair(plan: RepairPlan) -> RepairResult:
    ev: list[str] = []
    health = plan.diagnose()
    ev.append(f"diagnose={health.value}")
    if health == Health.OK:
        return RepairResult(plan.component, RepairOutcome.NOT_NEEDED, 0, tuple(ev))
    if health == Health.BLOCKED:
        return RepairResult(plan.component, RepairOutcome.BLOCKED, 0, tuple(ev))

    if plan.backup is not None:
        if not plan.backup():
            # HARD STOP: never repair without a backup when one is required.
            ev.append("backup=refused -> abort (no destructive repair)")
            return RepairResult(plan.component, RepairOutcome.BLOCKED, 0, tuple(ev))
        ev.append("backup=ok")

    attempts = 0
    for _ in range(max(1, plan.max_attempts)):
        attempts += 1
        applied = False
        try:
            applied = plan.repair() and plan.verify()
        except Exception as exc:  # pragma: no cover - defensive
            ev.append(f"repair_exception={type(exc).__name__}")
            applied = False
        if applied:
            ev.append(f"repair=ok attempt={attempts}")
            return RepairResult(plan.component, RepairOutcome.REPAIRED, attempts, tuple(ev))
        ev.append(f"repair=failed attempt={attempts}")

    # all attempts failed -> roll back the minimal component
    rolled = False
    try:
        rolled = plan.rollback() and (plan.verify() or plan.diagnose() != Health.FAIL)
    except Exception:  # pragma: no cover
        rolled = False
    if rolled:
        ev.append("rollback=ok")
        return RepairResult(plan.component, RepairOutcome.ROLLED_BACK, attempts, tuple(ev))
    ev.append("rollback=failed")
    return RepairResult(plan.component, RepairOutcome.ROLLBACK_FAILED, attempts, tuple(ev))


__all__ = ["Health", "RepairOutcome", "RepairPlan", "RepairResult", "run_repair"]
