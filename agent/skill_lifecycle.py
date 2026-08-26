"""Skill lifecycle + improvement proposals (Wave 6, §53/§57).

Extends the existing skill system's ACTIVE/STALE/ARCHIVED with the authoring
state machine the mission wants, plus separation-of-powers promotion gates and
an ImprovementProposal record (detect -> propose -> review -> integrate; never
detect -> edit production -> declare done). Pure state machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum


class SkillState(str, Enum):
    DRAFT = "DRAFT"
    TESTING = "TESTING"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    QUARANTINED = "QUARANTINED"   # security holding pen


@dataclass(frozen=True)
class SkillRecord:
    id: str
    version: str = "0.1.0"
    state: SkillState = SkillState.DRAFT
    origin: str = "agent"          # agent | hub | user
    has_tests: bool = False
    security_reviewed: bool = False
    benchmarked: bool = False
    permissions: tuple[str, ...] = ()


# Allowed transitions and the gate each requires.
def _gate(record: SkillRecord, target: SkillState) -> tuple[bool, str]:
    s = record.state
    if target == SkillState.QUARANTINED:
        return True, "quarantine always allowed (security)"
    if s == SkillState.QUARANTINED and target != SkillState.DRAFT:
        return False, "quarantined skills may only return to DRAFT after review"
    if s == SkillState.DRAFT and target == SkillState.TESTING:
        return True, "ok"
    if s == SkillState.TESTING and target == SkillState.APPROVED:
        if not record.has_tests:
            return False, "cannot APPROVE without tests"
        if record.origin != "user" and not record.security_reviewed:
            return False, "agent/hub skill needs security review to APPROVE"
        return True, "ok"
    if s == SkillState.APPROVED and target == SkillState.ACTIVE:
        if not record.benchmarked:
            return False, "cannot ACTIVATE without a benchmark"
        return True, "ok"
    if s == SkillState.ACTIVE and target == SkillState.DEPRECATED:
        return True, "ok"
    if s == SkillState.QUARANTINED and target == SkillState.DRAFT:
        return True, "ok"
    return False, f"illegal transition {s.value}->{target.value}"


def can_promote(record: SkillRecord, target: SkillState) -> tuple[bool, str]:
    return _gate(record, target)


def promote(record: SkillRecord, target: SkillState) -> SkillRecord:
    ok, reason = _gate(record, target)
    if not ok:
        raise ValueError(reason)
    return replace(record, state=target)


class ProposalState(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    INTEGRATED = "INTEGRATED"


@dataclass(frozen=True)
class ImprovementProposal:
    id: str
    target_skill: str
    rationale: str
    diff_ref: str | None = None
    state: ProposalState = ProposalState.PROPOSED

    def review(self, approve: bool) -> "ImprovementProposal":
        return replace(self, state=ProposalState.APPROVED if approve else ProposalState.REJECTED)

    def integrate(self) -> "ImprovementProposal":
        # separation of powers: cannot integrate what was not independently approved
        if self.state != ProposalState.APPROVED:
            raise ValueError("proposal must be APPROVED (independent review) before integration")
        return replace(self, state=ProposalState.INTEGRATED)


__all__ = [
    "SkillState", "SkillRecord", "can_promote", "promote",
    "ProposalState", "ImprovementProposal",
]
