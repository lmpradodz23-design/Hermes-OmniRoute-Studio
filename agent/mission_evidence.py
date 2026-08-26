"""Per-node evidence requirements (Wave 1/5, §12/§79).

The mission's hard rule: a node cannot be PASS without the evidence its kind
requires; missing evidence is UNVERIFIED, never PASS. This module makes that a
typed contract the Mission runtime consults when deciding whether a completed
node may be marked DONE.

It reuses the idea of the existing exit-code-anchored verification-evidence
ledger (agent/verification_evidence.py): an evidence item is a reference + an
``ok`` flag (bound to a real check), not free text. Pure module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping, Sequence


class EvidenceKind(str, Enum):
    TEST = "TEST"
    DIFF = "DIFF"
    COMMAND_RESULT = "COMMAND_RESULT"
    VISUAL = "VISUAL"
    BROWSER_STATE = "BROWSER_STATE"
    SCAN = "SCAN"
    RESCAN = "RESCAN"
    BUILD = "BUILD"
    INSTALLER = "INSTALLER"
    SMOKE = "SMOKE"


class Verification(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"   # required evidence missing -> NOT pass
    FAILED = "FAILED"           # required evidence present but failing


# Default required-evidence profiles by node role (§12). Small tasks can require
# nothing; heavy roles require proof appropriate to their risk.
DEFAULT_REQUIREMENTS: dict[str, tuple[EvidenceKind, ...]] = {
    "MICRO": (),
    "CODING": (EvidenceKind.TEST, EvidenceKind.DIFF, EvidenceKind.COMMAND_RESULT),
    "FRONTEND": (EvidenceKind.TEST, EvidenceKind.VISUAL, EvidenceKind.BROWSER_STATE),
    "BACKEND": (EvidenceKind.TEST, EvidenceKind.COMMAND_RESULT),
    "SECURITY": (EvidenceKind.SCAN, EvidenceKind.RESCAN),
    "RELEASE": (EvidenceKind.BUILD, EvidenceKind.INSTALLER, EvidenceKind.SMOKE),
}


@dataclass(frozen=True)
class EvidenceItem:
    kind: EvidenceKind
    ref: str            # a pointer (ledger id, artifact path, command id) — never a secret
    ok: bool = True     # bound to a real check (e.g. exit_code == 0)


@dataclass(frozen=True)
class VerificationResult:
    status: Verification
    missing: tuple[EvidenceKind, ...] = ()
    failing: tuple[EvidenceKind, ...] = ()

    @property
    def is_pass(self) -> bool:
        return self.status is Verification.VERIFIED


def required_for(role: str) -> tuple[EvidenceKind, ...]:
    """Default required-evidence set for a node role (empty for unknown/MICRO)."""
    return DEFAULT_REQUIREMENTS.get(role.upper(), ())


def verify_node(
    required: Iterable[EvidenceKind],
    provided: Sequence[EvidenceItem],
) -> VerificationResult:
    """Decide a node's verification status from its required kinds + provided items.

    VERIFIED  : every required kind is present AND all its items are ok.
    FAILED    : a required kind is present but at least one of its items failed.
    UNVERIFIED: a required kind has no evidence at all (default-deny — never PASS).
    """
    required_set = set(required)
    if not required_set:
        return VerificationResult(Verification.VERIFIED)

    present: dict[EvidenceKind, list[EvidenceItem]] = {}
    for item in provided:
        present.setdefault(item.kind, []).append(item)

    missing = tuple(sorted((k for k in required_set if k not in present), key=lambda k: k.value))
    failing = tuple(
        sorted(
            (k for k in required_set if k in present and not all(i.ok for i in present[k])),
            key=lambda k: k.value,
        )
    )
    if failing:
        return VerificationResult(Verification.FAILED, missing=missing, failing=failing)
    if missing:
        return VerificationResult(Verification.UNVERIFIED, missing=missing)
    return VerificationResult(Verification.VERIFIED)


__all__ = [
    "EvidenceKind", "Verification", "EvidenceItem", "VerificationResult",
    "DEFAULT_REQUIREMENTS", "required_for", "verify_node",
]
