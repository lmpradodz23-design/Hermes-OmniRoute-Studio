"""MCP control plane — tool registry + per-mission selection (§7/§29).

Extends (does not duplicate) the capability metadata idea: each tool carries
id/version/owner/risk/capability/health/latency/last_success/last_failure/
sandbox_requirement/permissions, and a mission receives ONLY the tools it needs
(not all 107 dumped into every context). Pure module — a later increment binds
it to the existing capabilities.lock / mcp_security registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class ToolRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ToolHealth(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


_RISK_ORDER = {ToolRisk.LOW: 0, ToolRisk.MEDIUM: 1, ToolRisk.HIGH: 2}


@dataclass(frozen=True)
class ToolMeta:
    id: str
    version: str = ""
    owner: str = ""
    capability: str = ""             # what task capability this tool provides
    risk: ToolRisk = ToolRisk.LOW
    health: ToolHealth = ToolHealth.OK
    latency_ms: float | None = None
    last_success: float | None = None
    last_failure: float | None = None
    sandbox_required: bool = False
    permissions: tuple[str, ...] = ()

    @property
    def usable(self) -> bool:
        return self.health != ToolHealth.DOWN


class ToolRegistry:
    def __init__(self, tools: Iterable[ToolMeta] = ()):
        self._tools: dict[str, ToolMeta] = {t.id: t for t in tools}

    def register(self, tool: ToolMeta) -> None:
        self._tools[tool.id] = tool

    def get(self, tool_id: str) -> ToolMeta | None:
        return self._tools.get(tool_id)

    def all(self) -> tuple[ToolMeta, ...]:
        return tuple(self._tools.values())

    def usable(self) -> tuple[ToolMeta, ...]:
        return tuple(t for t in self._tools.values() if t.usable)

    def select_for_mission(
        self,
        required_capabilities: Iterable[str],
        *,
        max_risk: ToolRisk = ToolRisk.HIGH,
    ) -> tuple[ToolMeta, ...]:
        """Return only the healthy tools whose capability the mission needs and
        whose risk is within ``max_risk`` — never the whole catalog."""
        caps = set(required_capabilities)
        cap_max = _RISK_ORDER[max_risk]
        out = [
            t for t in self._tools.values()
            if t.usable and t.capability in caps and _RISK_ORDER[t.risk] <= cap_max
        ]
        out.sort(key=lambda t: (t.capability, _RISK_ORDER[t.risk]))
        return tuple(out)


__all__ = ["ToolRisk", "ToolHealth", "ToolMeta", "ToolRegistry"]
