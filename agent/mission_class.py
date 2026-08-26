"""Adaptive pipeline classification (Wave 3, §67).

A 2-line fix must not trigger the whole software factory; a full product must.
This classifies a mission and returns the pipeline stages that apply, so the
planner scales the gate set to the work. Security invariants are never removed.
Pure module.
"""

from __future__ import annotations

from enum import Enum


class MissionClass(str, Enum):
    MICRO = "MICRO"          # tiny reversible change
    STANDARD = "STANDARD"    # normal feature/bugfix
    COMPLEX = "COMPLEX"      # multi-component change
    PRODUCT = "PRODUCT"      # build a product end to end
    HIGH_RISK = "HIGH_RISK"  # touches security/data/irreversible surfaces


# Pipeline stages (a superset; each class selects a subset).
STAGES = (
    "research", "spec", "architecture", "design", "implement", "integration",
    "test", "visual_qa", "security", "performance", "package", "install",
    "e2e", "evidence", "release",
)

_PIPELINES: dict[MissionClass, tuple[str, ...]] = {
    MissionClass.MICRO: ("implement", "test", "evidence"),
    MissionClass.STANDARD: ("spec", "implement", "test", "security", "evidence"),
    MissionClass.COMPLEX: ("spec", "architecture", "implement", "integration", "test",
                           "security", "evidence"),
    MissionClass.PRODUCT: STAGES,
    MissionClass.HIGH_RISK: ("spec", "architecture", "implement", "integration", "test",
                             "visual_qa", "security", "performance", "e2e", "evidence", "release"),
}

# Stages that are ALWAYS present regardless of class (never dropped).
_MANDATORY = frozenset({"test", "evidence"})


def classify(
    *,
    feature_count: int = 0,
    touches_security: bool = False,
    touches_data_or_irreversible: bool = False,
    is_product: bool = False,
    files_changed: int = 0,
) -> MissionClass:
    if touches_security or touches_data_or_irreversible:
        return MissionClass.HIGH_RISK
    if is_product or feature_count >= 4:
        return MissionClass.PRODUCT
    if feature_count >= 2 or files_changed >= 8:
        return MissionClass.COMPLEX
    if feature_count == 1 or files_changed >= 2:
        return MissionClass.STANDARD
    return MissionClass.MICRO


def pipeline_gates(mission_class: MissionClass) -> tuple[str, ...]:
    gates = _PIPELINES[mission_class]
    # guarantee mandatory stages are present, preserving canonical order
    out = [s for s in STAGES if s in set(gates) | _MANDATORY]
    return tuple(out)


def security_required(mission_class: MissionClass) -> bool:
    return "security" in pipeline_gates(mission_class)


__all__ = ["MissionClass", "STAGES", "classify", "pipeline_gates", "security_required"]
