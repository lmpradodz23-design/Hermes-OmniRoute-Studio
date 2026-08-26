"""The thin Mission entity (Wave 1, §6 Autonomy Kernel).

WAVE ZERO found two disjoint autonomy engines — the per-session Goal loop
(``hermes_cli/goals.py``, durable in ``state.db``) and the multi-task Kanban DAG
(``hermes_cli/kanban_db.py``) — with no unifying record. Building a third loop
would be duplication. Instead, a ``Mission`` is a *reference*: it points at an
existing ``GoalState`` key and/or a Kanban board id, and carries a single derived
state so a checkpoint and a stuck-signal span both engines.

This module is pure (no I/O). ``to_dict``/``from_dict`` give a durable form the
caller persists via the existing ``state.db state_meta`` path; ``derive_state``
composes the other Wave-1 primitives (DAG frontier + budget + progress) into one
``MissionState`` without running anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Mapping

from agent.budget_state import BudgetState
from agent.progress_signal import ProgressSignal


class MissionState(str, Enum):
    DRAFT = "DRAFT"
    PLANNING = "PLANNING"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_DEPENDENCY = "WAITING_DEPENDENCY"
    WAITING_TOOL = "WAITING_TOOL"
    WAITING_AGENT = "WAITING_AGENT"
    WAITING_HUMAN = "WAITING_HUMAN"
    BLOCKED = "BLOCKED"
    RETRYING = "RETRYING"
    VERIFYING = "VERIFYING"
    REPAIRING = "REPAIRING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


_TERMINAL = {MissionState.COMPLETED, MissionState.FAILED, MissionState.CANCELLED}


@dataclass(frozen=True)
class Mission:
    """A reference record binding the existing engines under one identity."""

    id: str
    title: str = ""
    state: MissionState = MissionState.DRAFT
    goal_key: str | None = None            # -> state.db state_meta "goal:<session>"
    kanban_board_id: str | None = None     # -> kanban board
    created_at: float | None = None
    updated_at: float | None = None
    human_gate: bool = False               # a human gate is currently pending
    meta: Mapping[str, Any] = field(default_factory=dict)

    def is_terminal(self) -> bool:
        return self.state in _TERMINAL

    def with_state(self, new_state: MissionState, *, at: float | None = None) -> "Mission":
        return replace(self, state=new_state, updated_at=at if at is not None else self.updated_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "state": self.state.value,
            "goal_key": self.goal_key,
            "kanban_board_id": self.kanban_board_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "human_gate": self.human_gate,
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Mission":
        return cls(
            id=str(data["id"]),
            title=str(data.get("title", "")),
            state=MissionState(data.get("state", MissionState.DRAFT.value)),
            goal_key=data.get("goal_key"),
            kanban_board_id=data.get("kanban_board_id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            human_gate=bool(data.get("human_gate", False)),
            meta=dict(data.get("meta", {}) or {}),
        )


@dataclass(frozen=True)
class Checkpoint:
    """A durable reference tuple — not a copy of state (§9).

    Reconstructing a Mission means reloading the referenced GoalState row and the
    Kanban board; this record only pins *which* rows to reload plus the last
    derived state, so the two stores can be reconciled idempotently on resume.
    """

    mission_id: str
    goal_key: str | None
    kanban_board_id: str | None
    state: MissionState
    at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "goal_key": self.goal_key,
            "kanban_board_id": self.kanban_board_id,
            "state": self.state.value,
            "at": self.at,
        }

    @classmethod
    def of(cls, mission: Mission, *, at: float | None = None) -> "Checkpoint":
        return cls(
            mission_id=mission.id,
            goal_key=mission.goal_key,
            kanban_board_id=mission.kanban_board_id,
            state=mission.state,
            at=at if at is not None else mission.updated_at,
        )


def derive_state(
    *,
    total_nodes: int,
    done_nodes: int,
    ready_nodes: int,
    failed: bool = False,
    cancelled: bool = False,
    awaiting_human: bool = False,
    budget: BudgetState | None = None,
    progress: ProgressSignal | None = None,
) -> MissionState:
    """Compose the Wave-1 primitives into one MissionState (pure).

    Precedence (most decisive first): explicit cancel/fail, human gate, hard
    budget breach, all-done, no runnable frontier (dependency wait), a stalled
    progress signal, else running/planning. This is deliberately small and
    deterministic so it can be unit-tested and reused by both engines.
    """
    if cancelled:
        return MissionState.CANCELLED
    if failed:
        return MissionState.FAILED
    if awaiting_human or budget == BudgetState.OVERRIDE_REQUIRED:
        return MissionState.WAITING_HUMAN
    if budget == BudgetState.LIMIT_REACHED:
        return MissionState.BLOCKED
    if total_nodes > 0 and done_nodes >= total_nodes:
        return MissionState.COMPLETED
    if progress == ProgressSignal.ESCALATE_TO_DIAGNOSTIC_AGENT:
        return MissionState.REPAIRING
    if progress == ProgressSignal.STRATEGY_CHANGE_REQUIRED:
        return MissionState.RETRYING
    if total_nodes > 0 and ready_nodes == 0 and done_nodes < total_nodes:
        # nothing dispatchable but work remains -> waiting on dependencies
        return MissionState.WAITING_DEPENDENCY
    if total_nodes == 0:
        return MissionState.PLANNING
    return MissionState.RUNNING


__all__ = ["MissionState", "Mission", "Checkpoint", "derive_state"]
