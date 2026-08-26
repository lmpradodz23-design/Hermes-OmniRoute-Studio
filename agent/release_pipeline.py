"""Release pipeline model — adaptive gates + evidence package (§49/§5).

Composes the existing pieces (mission_class pipeline stages + mission_evidence
required-evidence) into a release readiness model: each stage declares the
evidence it needs, and the release is READY only when every required stage has
its evidence. Does NOT create a parallel CI — it's the gate model the existing
workflows feed. Pure module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from agent.mission_class import MissionClass, pipeline_gates
from agent.mission_evidence import EvidenceItem, EvidenceKind, Verification, verify_node


# Which evidence each release stage requires.
STAGE_EVIDENCE: dict[str, tuple[EvidenceKind, ...]] = {
    "implement": (EvidenceKind.DIFF,),
    "test": (EvidenceKind.TEST,),
    "security": (EvidenceKind.SCAN,),
    "visual_qa": (EvidenceKind.VISUAL,),
    "e2e": (EvidenceKind.SMOKE,),
    "package": (EvidenceKind.BUILD,),
    "install": (EvidenceKind.INSTALLER,),
    "evidence": (),  # the packaging stage itself
    "release": (),
}


@dataclass(frozen=True)
class StageResult:
    stage: str
    status: Verification


@dataclass(frozen=True)
class ReleaseVerdict:
    ready: bool
    stages: tuple[StageResult, ...]
    blocking_stages: tuple[str, ...]


def evaluate_release(
    mission_class: MissionClass,
    provided: Mapping[str, Iterable[EvidenceItem]],
) -> ReleaseVerdict:
    """Evaluate release readiness for the class's pipeline given per-stage evidence."""
    gates = pipeline_gates(mission_class)
    results: list[StageResult] = []
    blocking: list[str] = []
    for stage in gates:
        required = STAGE_EVIDENCE.get(stage, ())
        items = list(provided.get(stage, ()))
        res = verify_node(required, items)
        results.append(StageResult(stage, res.status))
        if res.status != Verification.VERIFIED:
            blocking.append(stage)
    return ReleaseVerdict(ready=not blocking, stages=tuple(results),
                          blocking_stages=tuple(blocking))


__all__ = ["STAGE_EVIDENCE", "StageResult", "ReleaseVerdict", "evaluate_release"]
