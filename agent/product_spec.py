"""Structured ProductSpec (Wave 3, §11/§16) + a bridge to the Mission DAG.

WAVE ZERO found that Product Studio's "spec" is free-form LLM prose — there is
no machine-readable ProductSpec anywhere in the tree (zero `ProductSpec` code
matches), so the design engine, specialists, and delivery gates cannot reliably
consume it. This module is that missing structured artifact: a validated,
serialisable spec that intake emits and that `to_mission_dag()` turns into a
concrete build graph the existing kernel (Mission DAG + dispatcher) can schedule.

Pure module: no I/O, stdlib + agent.mission_dag only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from agent.mission_dag import DagNode, MissionDag


_PRIORITY_WEIGHT = {"low": 1.0, "medium": 2.0, "high": 3.0, "critical": 5.0}


@dataclass(frozen=True)
class Feature:
    id: str
    title: str
    priority: str = "medium"          # low|medium|high|critical
    depends_on: tuple[str, ...] = ()   # other feature ids

    @property
    def weight(self) -> float:
        return _PRIORITY_WEIGHT.get(self.priority.lower(), 2.0)


@dataclass(frozen=True)
class ProductSpec:
    """A machine-readable product specification (§16 fields)."""

    name: str
    summary: str = ""
    audience: str = ""
    roles: tuple[str, ...] = ()
    features: tuple[Feature, ...] = ()
    journeys: tuple[str, ...] = ()
    design_direction: str = ""
    frontend: str = ""
    backend: str = ""
    database: str = ""
    auth: str = ""
    integrations: tuple[str, ...] = ()
    platforms: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()   # "DECISAO ASSUMIDA: ..." records
    risks: tuple[str, ...] = ()
    schema_version: int = 1

    # ---- validation ----------------------------------------------------- #

    def validate(self) -> list[str]:
        """Return a list of problems ([] == valid). Never raises."""
        issues: list[str] = []
        if not self.name.strip():
            issues.append("name is required")
        if not self.acceptance_criteria:
            issues.append("at least one acceptance_criteria is required")
        if not self.platforms:
            issues.append("at least one target platform is required")
        ids = [f.id for f in self.features]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            issues.append(f"duplicate feature ids: {sorted(dupes)}")
        idset = set(ids)
        for f in self.features:
            if not f.id.strip():
                issues.append("a feature has an empty id")
            for dep in f.depends_on:
                if dep not in idset:
                    issues.append(f"feature {f.id!r} depends on unknown feature {dep!r}")
        bad_prio = [f.id for f in self.features if f.priority.lower() not in _PRIORITY_WEIGHT]
        if bad_prio:
            issues.append(f"features with invalid priority: {bad_prio}")
        return issues

    @property
    def is_valid(self) -> bool:
        return not self.validate()

    # ---- serialisation -------------------------------------------------- #

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "summary": self.summary,
            "audience": self.audience,
            "roles": list(self.roles),
            "features": [
                {"id": f.id, "title": f.title, "priority": f.priority,
                 "depends_on": list(f.depends_on)}
                for f in self.features
            ],
            "journeys": list(self.journeys),
            "design_direction": self.design_direction,
            "frontend": self.frontend,
            "backend": self.backend,
            "database": self.database,
            "auth": self.auth,
            "integrations": list(self.integrations),
            "platforms": list(self.platforms),
            "acceptance_criteria": list(self.acceptance_criteria),
            "assumptions": list(self.assumptions),
            "risks": list(self.risks),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ProductSpec":
        def _tuple(key: str) -> tuple[str, ...]:
            return tuple(str(x) for x in (data.get(key) or ()))

        features = tuple(
            Feature(
                id=str(f["id"]),
                title=str(f.get("title", "")),
                priority=str(f.get("priority", "medium")),
                depends_on=tuple(str(d) for d in (f.get("depends_on") or ())),
            )
            for f in (data.get("features") or ())
        )
        return cls(
            name=str(data.get("name", "")),
            summary=str(data.get("summary", "")),
            audience=str(data.get("audience", "")),
            roles=_tuple("roles"),
            features=features,
            journeys=_tuple("journeys"),
            design_direction=str(data.get("design_direction", "")),
            frontend=str(data.get("frontend", "")),
            backend=str(data.get("backend", "")),
            database=str(data.get("database", "")),
            auth=str(data.get("auth", "")),
            integrations=_tuple("integrations"),
            platforms=_tuple("platforms"),
            acceptance_criteria=_tuple("acceptance_criteria"),
            assumptions=_tuple("assumptions"),
            risks=_tuple("risks"),
            schema_version=int(data.get("schema_version", 1)),
        )

    # ---- bridge to the kernel ------------------------------------------- #

    def to_mission_dag(
        self,
        *,
        include_qa: bool = True,
        include_release: bool = True,
    ) -> MissionDag:
        """Turn the spec into a schedulable build graph (§45 pipeline).

        Each feature becomes a node (edges = ``depends_on``). A single QA node
        depends on every feature; a RELEASE node depends on QA. This is the
        smallest faithful mapping onto the existing Mission DAG so the existing
        dispatcher can schedule it — the planner may refine it further.
        """
        if not self.is_valid:
            raise ValueError(f"cannot build DAG from invalid spec: {self.validate()}")
        nodes: list[DagNode] = []
        for f in self.features:
            nodes.append(
                DagNode(id=f.id, parents=f.depends_on, weight=f.weight, label=f.title)
            )
        feature_ids = tuple(f.id for f in self.features)
        tail: str | None = None
        if include_qa and feature_ids:
            nodes.append(DagNode(id="__qa__", parents=feature_ids, weight=2.0, label="QA"))
            tail = "__qa__"
        if include_release:
            parents = (tail,) if tail else feature_ids
            nodes.append(
                DagNode(id="__release__", parents=parents, weight=1.0, label="Release candidate")
            )
        return MissionDag(nodes)


__all__ = ["Feature", "ProductSpec"]
