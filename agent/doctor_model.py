"""Doctor health-report model (Wave 6, §54).

A composable health model that extends hermes doctor's vocabulary with a BLOCKED
status and a structured (status + root cause + evidence + repair candidate) per
check, and bridges FAIL checks to SafeRepair / the self-heal loop. This is the
LOGIC layer (pure, testable) that the existing 4000-line doctor.py can adopt —
NOT a DoctorV2 and NOT an edit to the runtime file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from agent.safe_repair import Health
from agent.self_heal import HealthSignal


class CheckStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"     # platform/external gated (the status doctor lacked)


_SEVERITY = {CheckStatus.PASS: 0, CheckStatus.WARN: 1, CheckStatus.BLOCKED: 2, CheckStatus.FAIL: 3}


@dataclass(frozen=True)
class CheckResult:
    component: str
    status: CheckStatus
    root_cause: str = ""
    evidence_ref: str | None = None
    repair_candidate: str | None = None    # component name a SafeRepair plan targets


@dataclass(frozen=True)
class DoctorReport:
    results: tuple[CheckResult, ...] = ()

    @property
    def overall(self) -> CheckStatus:
        worst = CheckStatus.PASS
        for r in self.results:
            if _SEVERITY[r.status] > _SEVERITY[worst]:
                worst = r.status
        return worst

    def failing(self) -> tuple[CheckResult, ...]:
        return tuple(r for r in self.results if r.status == CheckStatus.FAIL)

    def blocked(self) -> tuple[CheckResult, ...]:
        return tuple(r for r in self.results if r.status == CheckStatus.BLOCKED)

    def repairable(self) -> tuple[CheckResult, ...]:
        return tuple(r for r in self.results
                     if r.status == CheckStatus.FAIL and r.repair_candidate)

    def to_health_signals(self) -> list[HealthSignal]:
        """Bridge FAIL checks into self-heal health signals (§54 -> §56)."""
        return [
            HealthSignal(component=r.repair_candidate or r.component, health=Health.FAIL,
                         detail=r.root_cause, evidence_ref=r.evidence_ref)
            for r in self.failing()
        ]


__all__ = ["CheckStatus", "CheckResult", "DoctorReport"]
