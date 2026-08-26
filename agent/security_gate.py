"""Security as a Mission gate (Wave 5, §47/§84/§85).

RAPTOR/security must participate in the DAG, not be a screen. A SECURITY_REVIEW
node produces findings; a validated P0/P1 finding creates a remediation node and
BLOCKS the release node until it is remediated AND a rescan confirms it is gone.
If a rescan re-surfaces a finding, the node reopens.

This composes the existing kernel (MissionDag dynamic nodes) with the security
primitives' state discipline (a finding is only CONFIRMED with reproducible
evidence — mirrors security_research/findings.py). Pure module; the actual scan
is an injected executor step, unit-testable with fakes (RAPTOR binary itself is
BLOCKED_BY_PLATFORM here).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Iterable, Sequence

from agent.mission_dag import DagNode, MissionDag


class Severity(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class FindingState(str, Enum):
    CANDIDATE = "CANDIDATE"       # not yet reproduced
    CONFIRMED = "CONFIRMED"       # reproducible FACT evidence
    REMEDIATED = "REMEDIATED"     # a fix was applied (pending rescan)
    RESOLVED = "RESOLVED"         # rescan confirmed gone


_BLOCKING_SEVERITY = frozenset({Severity.P0, Severity.P1})


@dataclass(frozen=True)
class SecurityFinding:
    id: str
    severity: Severity
    title: str = ""
    state: FindingState = FindingState.CANDIDATE
    evidence_ref: str | None = None   # a reproducible FACT reference

    @property
    def is_confirmed(self) -> bool:
        # a finding may only be CONFIRMED with reproducible evidence
        return self.state == FindingState.CONFIRMED and bool(self.evidence_ref)

    @property
    def blocks_release(self) -> bool:
        return self.severity in _BLOCKING_SEVERITY and self.state != FindingState.RESOLVED


def validate(findings: Iterable[SecurityFinding]) -> tuple[SecurityFinding, ...]:
    """The confirmed, still-open blocking findings (P0/P1 with evidence)."""
    return tuple(f for f in findings if f.severity in _BLOCKING_SEVERITY and f.is_confirmed)


def release_blocked(findings: Iterable[SecurityFinding]) -> bool:
    return any(f.blocks_release for f in findings)


def remediation_node_id(finding_id: str) -> str:
    return f"__remediate__{finding_id}"


RESCAN_NODE = "__security_rescan__"


def apply_security_gate(
    dag: MissionDag,
    *,
    security_node: str,
    release_node: str,
    findings: Sequence[SecurityFinding],
) -> MissionDag:
    """Inject a remediation node per confirmed blocking finding + a rescan node,
    and make the release node depend on the rescan (so it cannot be READY until
    remediation + rescan pass). No-op if there are no blocking findings."""
    if security_node not in dag or release_node not in dag:
        raise KeyError("security_node and release_node must exist in the DAG")
    blocking = validate(findings)
    if not blocking:
        return dag

    remediation_ids = [remediation_node_id(f.id) for f in blocking]
    nodes: list[DagNode] = []
    for nid in dag.ids():
        node = dag.node(nid)
        if nid == release_node:
            node = replace(node, parents=tuple(node.parents) + (RESCAN_NODE,))
        nodes.append(node)
    for f, rid in zip(blocking, remediation_ids):
        nodes.append(DagNode(id=rid, parents=(security_node,), weight=2.0,
                             label=f"Remediate {f.severity.value}: {f.title or f.id}"))
    nodes.append(DagNode(id=RESCAN_NODE, parents=tuple(remediation_ids), weight=1.0,
                         label="Security rescan"))
    return MissionDag(nodes)


def rescan(
    previously_confirmed: Iterable[SecurityFinding],
    current_findings: Iterable[SecurityFinding],
) -> tuple[SecurityFinding, ...]:
    """Findings that REAPPEAR after remediation must reopen the node (§84).

    Returns the subset of ``previously_confirmed`` whose id is still present
    (confirmed) in ``current_findings`` — those reopen; anything absent is cleared.
    """
    current_ids = {f.id for f in current_findings if f.is_confirmed}
    return tuple(f for f in previously_confirmed if f.id in current_ids)


__all__ = [
    "Severity", "FindingState", "SecurityFinding",
    "validate", "release_blocked", "apply_security_gate", "rescan",
    "remediation_node_id", "RESCAN_NODE",
]
