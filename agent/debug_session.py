"""Debugging engine — a disciplined debug session (Wave 4, §45).

Enforces the Iron Law: NO FIXES WITHOUT ROOT CAUSE. A DebugSession walks
REPRODUCE -> OBSERVE -> HYPOTHESIS -> TEST -> ROOT_CAUSE -> PATCH -> VERIFY and
refuses out-of-order transitions (e.g. patching before a root cause is
established, or resolving before verification passes). Pure state machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DebugState(str, Enum):
    NEW = "NEW"
    REPRODUCED = "REPRODUCED"
    OBSERVED = "OBSERVED"
    HYPOTHESIZING = "HYPOTHESIZING"
    ROOT_CAUSED = "ROOT_CAUSED"
    PATCHED = "PATCHED"
    VERIFIED = "VERIFIED"
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class Hypothesis:
    text: str
    supported: bool | None = None


@dataclass(frozen=True)
class RootCause:
    text: str
    evidence_ref: str


class DebugError(RuntimeError):
    pass


class DebugSession:
    def __init__(self, symptom: str) -> None:
        self.symptom = symptom
        self.state = DebugState.NEW
        self.observations: list[str] = []
        self.hypotheses: list[Hypothesis] = []
        self.root_cause: RootCause | None = None
        self.patch_ref: str | None = None

    def reproduce(self, ok: bool) -> None:
        if not ok:
            self.state = DebugState.FAILED     # cannot debug what you can't reproduce
            raise DebugError("could not reproduce — cannot proceed to a fix")
        self.state = DebugState.REPRODUCED

    def observe(self, observation: str) -> None:
        if self.state == DebugState.NEW:
            raise DebugError("reproduce before observing")
        self.observations.append(observation)
        self.state = DebugState.OBSERVED

    def hypothesize(self, text: str) -> Hypothesis:
        if self.state in (DebugState.NEW, DebugState.FAILED):
            raise DebugError("reproduce+observe before hypothesizing")
        h = Hypothesis(text)
        self.hypotheses.append(h)
        self.state = DebugState.HYPOTHESIZING
        return h

    def test_hypothesis(self, hypothesis: Hypothesis, supported: bool) -> None:
        if self.state != DebugState.HYPOTHESIZING:
            raise DebugError("no hypothesis under test")
        idx = self.hypotheses.index(hypothesis)
        self.hypotheses[idx] = Hypothesis(hypothesis.text, supported)

    def set_root_cause(self, text: str, evidence_ref: str) -> None:
        if not any(h.supported for h in self.hypotheses):
            raise DebugError("a root cause needs a supported hypothesis (evidence)")
        self.root_cause = RootCause(text, evidence_ref)
        self.state = DebugState.ROOT_CAUSED

    def apply_patch(self, patch_ref: str) -> None:
        # Iron Law: no fix without a root cause.
        if self.root_cause is None or self.state != DebugState.ROOT_CAUSED:
            raise DebugError("NO FIXES WITHOUT ROOT CAUSE")
        self.patch_ref = patch_ref
        self.state = DebugState.PATCHED

    def verify(self, ok: bool) -> DebugState:
        if self.state != DebugState.PATCHED:
            raise DebugError("nothing patched to verify")
        if ok:
            self.state = DebugState.VERIFIED
            self.state = DebugState.RESOLVED
        else:
            # patch didn't fix it — back to hypothesizing, root cause invalidated
            self.root_cause = None
            self.patch_ref = None
            self.state = DebugState.HYPOTHESIZING
        return self.state


__all__ = ["DebugState", "Hypothesis", "RootCause", "DebugError", "DebugSession"]
