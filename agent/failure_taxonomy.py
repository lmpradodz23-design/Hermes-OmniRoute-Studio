"""Failure taxonomy + recommended scheduler action (Wave 1, §64).

Standardizes failure classification so the scheduler/replanner reacts correctly
(retry vs replan vs acquire vs human-gate vs blocked). Pure classifier; reuses
the capability-acquisition detector for the MISSING_CAPABILITY signal.
"""

from __future__ import annotations

import re
from enum import Enum

from agent.capability_acquisition import looks_like_missing_capability


class FailureType(str, Enum):
    INTERNAL_BUG = "INTERNAL_BUG"
    MODEL_FAILURE = "MODEL_FAILURE"
    TOOL_FAILURE = "TOOL_FAILURE"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    ENVIRONMENT_FAILURE = "ENVIRONMENT_FAILURE"
    EXTERNAL_DEPENDENCY = "EXTERNAL_DEPENDENCY"
    SECURITY_BLOCK = "SECURITY_BLOCK"
    HUMAN_GATE = "HUMAN_GATE"
    PLATFORM_LIMITATION = "PLATFORM_LIMITATION"
    TIMEOUT = "TIMEOUT"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    MISSING_CAPABILITY = "MISSING_CAPABILITY"


# Recommended scheduler action per failure type (§64/§65).
RECOMMENDED_ACTION: dict[FailureType, str] = {
    FailureType.INTERNAL_BUG: "replan",
    FailureType.MODEL_FAILURE: "retry",
    FailureType.TOOL_FAILURE: "retry",
    FailureType.PROVIDER_FAILURE: "reassign_provider",
    FailureType.ENVIRONMENT_FAILURE: "repair_env",
    FailureType.EXTERNAL_DEPENDENCY: "blocked_external",
    FailureType.SECURITY_BLOCK: "abort",
    FailureType.HUMAN_GATE: "human_gate",
    FailureType.PLATFORM_LIMITATION: "blocked_platform",
    FailureType.TIMEOUT: "retry",
    FailureType.BUDGET_EXCEEDED: "human_gate",
    FailureType.MISSING_CAPABILITY: "acquire_capability",
}

_PATTERNS: tuple[tuple[re.Pattern[str], FailureType], ...] = tuple(
    (re.compile(p, re.IGNORECASE), t)
    for p, t in (
        (r"\btimed?\s*out\b|deadline exceeded", FailureType.TIMEOUT),
        (r"budget|spend ceiling|LIMIT_REACHED|quota exceeded", FailureType.BUDGET_EXCEEDED),
        (r"local[- ]only|blocked.*network|security policy|forbidden by policy", FailureType.SECURITY_BLOCK),
        (r"human gate|requires confirmation|awaiting approval", FailureType.HUMAN_GATE),
        (r"requires (?:macos|xcode|windows)|not supported on this platform", FailureType.PLATFORM_LIMITATION),
        (r"credential|api key missing|paid|account required|external service", FailureType.EXTERNAL_DEPENDENCY),
        (r"rate limit|provider .*unavailable|upstream error|502|503|529", FailureType.PROVIDER_FAILURE),
        (r"connection refused|no space left|permission denied|disk", FailureType.ENVIRONMENT_FAILURE),
        (r"tool .*failed|non-zero exit|subprocess error", FailureType.TOOL_FAILURE),
        (r"model (?:refused|returned invalid|hallucinat)", FailureType.MODEL_FAILURE),
    )
)


def classify(reason: str) -> FailureType:
    text = reason or ""
    if looks_like_missing_capability(text):
        return FailureType.MISSING_CAPABILITY
    for pattern, ftype in _PATTERNS:
        if pattern.search(text):
            return ftype
    return FailureType.INTERNAL_BUG


def recommended_action(ftype: FailureType) -> str:
    return RECOMMENDED_ACTION[ftype]


__all__ = ["FailureType", "RECOMMENDED_ACTION", "classify", "recommended_action"]
