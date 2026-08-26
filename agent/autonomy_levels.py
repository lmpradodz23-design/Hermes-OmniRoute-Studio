"""Autonomy levels + action gating policy (Wave 1, §62/§63).

Backend-enforced autonomy policy: given the mission's autonomy level and the
risk class of an action, decide ALLOW / PROPOSE / HUMAN_GATE / DENY. High
autonomy never means "no control" — destructive / financial / release / secret
actions always require a human gate, and untrusted input can never raise the
level. Pure policy module.
"""

from __future__ import annotations

from enum import Enum


class AutonomyLevel(str, Enum):
    ASSIST = "ASSIST"                       # proposes; human executes/approves often
    EXECUTE = "EXECUTE"                     # does local/reversible work
    AUTONOMOUS = "AUTONOMOUS"               # plans/delegates/fixes within policy
    PRODUCTION_GUARDED = "PRODUCTION_GUARDED"  # high autonomy; external/irreversible gated


class ActionClass(str, Enum):
    READ_ONLY = "READ_ONLY"
    LOCAL_REVERSIBLE = "LOCAL_REVERSIBLE"
    LOCAL_IRREVERSIBLE = "LOCAL_IRREVERSIBLE"
    EXTERNAL_REVERSIBLE = "EXTERNAL_REVERSIBLE"
    EXTERNAL_IRREVERSIBLE = "EXTERNAL_IRREVERSIBLE"
    DESTRUCTIVE = "DESTRUCTIVE"
    FINANCIAL = "FINANCIAL"
    RELEASE_PUBLISH = "RELEASE_PUBLISH"
    SECRET_ROTATION = "SECRET_ROTATION"


class Decision(str, Enum):
    ALLOW = "ALLOW"
    PROPOSE = "PROPOSE"        # do not execute; hand a ready proposal to the human
    HUMAN_GATE = "HUMAN_GATE"  # requires explicit human confirmation
    DENY = "DENY"


# Actions that ALWAYS require a human gate regardless of level (§63).
_ALWAYS_GATED = frozenset({
    ActionClass.DESTRUCTIVE,
    ActionClass.FINANCIAL,
    ActionClass.RELEASE_PUBLISH,
    ActionClass.SECRET_ROTATION,
})

_LOCAL = frozenset({ActionClass.READ_ONLY, ActionClass.LOCAL_REVERSIBLE, ActionClass.LOCAL_IRREVERSIBLE})


def decide(level: AutonomyLevel, action: ActionClass) -> Decision:
    """Backend policy decision (never overridable by untrusted input)."""
    if action in _ALWAYS_GATED:
        return Decision.HUMAN_GATE

    if level == AutonomyLevel.ASSIST:
        return Decision.ALLOW if action == ActionClass.READ_ONLY else Decision.PROPOSE

    if level == AutonomyLevel.EXECUTE:
        if action in (ActionClass.READ_ONLY, ActionClass.LOCAL_REVERSIBLE):
            return Decision.ALLOW
        return Decision.HUMAN_GATE

    if level == AutonomyLevel.AUTONOMOUS:
        if action in _LOCAL:
            return Decision.ALLOW
        return Decision.HUMAN_GATE   # any external action gated

    if level == AutonomyLevel.PRODUCTION_GUARDED:
        if action in _LOCAL or action == ActionClass.EXTERNAL_REVERSIBLE:
            return Decision.ALLOW
        return Decision.HUMAN_GATE   # external irreversible gated

    return Decision.HUMAN_GATE


def requires_human(level: AutonomyLevel, action: ActionClass) -> bool:
    return decide(level, action) == Decision.HUMAN_GATE


__all__ = ["AutonomyLevel", "ActionClass", "Decision", "decide", "requires_human"]
