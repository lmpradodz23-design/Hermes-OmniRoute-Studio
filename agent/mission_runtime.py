"""Mission orchestration (Wave 1, §3/§5): scheduler + watchdog + recovery.

This is the thin runtime that makes the kernel primitives coherent: it walks a
persisted Mission DAG, dispatches ready nodes to a pluggable executor (in real
runtime that executor delegates to the existing Goal loop / Kanban dispatcher /
subagents — NOT a new engine), records status + evidence references + events,
derives the Mission state, applies a bounded recovery policy (never infinite
retry), and checkpoints after every step so a restart can resume.

Pure orchestration; all persistence goes through ``MissionStore`` and all state
math through the existing ``mission`` / ``mission_dag`` / ``progress_signal``
primitives. Time is injected (``now_fn``) for determinism and resume-safety.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from agent.mission import Checkpoint, Mission, MissionState, derive_state
from agent.mission_store import MissionStore
from agent.progress_signal import ProgressSignal


# node status vocabulary (persisted as text)
PENDING, RUNNING, DONE, FAILED, BLOCKED = "pending", "running", "done", "failed", "blocked"


@dataclass(frozen=True)
class NodeOutcome:
    ok: bool
    evidence_ref: str | None = None
    failure_type: str | None = None


NodeExecutor = Callable[[str, str], NodeOutcome]  # (mission_id, node_id) -> outcome


@dataclass(frozen=True)
class RecoveryPolicy:
    max_attempts: int = 3

    def should_retry(self, attempts: int) -> bool:
        return attempts < self.max_attempts


class WatchdogStatus(str, Enum):
    HEALTHY = "HEALTHY"
    SLOW = "SLOW"
    STUCK = "STUCK"
    FAILED = "FAILED"
    RECOVERABLE = "RECOVERABLE"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class WatchdogVerdict:
    status: WatchdogStatus
    action: str   # retry | reassign | replan | pause | human_gate | none


def watchdog(
    *,
    progress: ProgressSignal,
    any_failed: bool,
    recoverable: bool,
    awaiting_human: bool,
    slow: bool = False,
) -> WatchdogVerdict:
    """Map progress + node health onto a watchdog verdict + action (§5)."""
    if awaiting_human:
        return WatchdogVerdict(WatchdogStatus.BLOCKED, "human_gate")
    if any_failed and not recoverable:
        return WatchdogVerdict(WatchdogStatus.FAILED, "replan")
    if any_failed and recoverable:
        return WatchdogVerdict(WatchdogStatus.RECOVERABLE, "retry")
    if progress == ProgressSignal.STALLED_NO_HEARTBEAT:
        return WatchdogVerdict(WatchdogStatus.STUCK, "reassign")
    if progress == ProgressSignal.ESCALATE_TO_DIAGNOSTIC_AGENT:
        return WatchdogVerdict(WatchdogStatus.STUCK, "replan")
    if progress == ProgressSignal.STRATEGY_CHANGE_REQUIRED:
        return WatchdogVerdict(WatchdogStatus.RECOVERABLE, "retry")
    if slow:
        return WatchdogVerdict(WatchdogStatus.SLOW, "none")
    return WatchdogVerdict(WatchdogStatus.HEALTHY, "none")


class MissionRuntime:
    def __init__(
        self,
        store: MissionStore,
        executor: NodeExecutor,
        *,
        now_fn: Callable[[], float],
        recovery: RecoveryPolicy | None = None,
    ):
        self.store = store
        self.executor = executor
        self.now = now_fn
        self.recovery = recovery or RecoveryPolicy()

    # ---- lifecycle ------------------------------------------------------ #

    def create(self, mission: Mission, dag) -> Mission:
        mission = mission.with_state(MissionState.READY, at=self.now())
        statuses = {nid: PENDING for nid in dag.ids()}
        self.store.save_mission(mission, dag, statuses)
        self.store.save_checkpoint(Checkpoint.of(mission, at=self.now()))
        self.store.append_event(mission.id, "created", {"nodes": list(dag.ids())}, at=self.now())
        return mission

    def _statuses(self, mission_id: str, dag) -> dict[str, str]:
        _, _, statuses = self.store.load_mission(mission_id)
        return statuses

    def _derive(self, dag, statuses: dict[str, str], *, awaiting_human: bool = False,
                progress: ProgressSignal = ProgressSignal.PROGRESSING) -> MissionState:
        done = {n for n, s in statuses.items() if s == DONE}
        failed = any(s == FAILED for s in statuses.values())
        ready = [n for n in dag.ready_nodes(done) if statuses.get(n) == PENDING]
        return derive_state(
            total_nodes=len(dag), done_nodes=len(done), ready_nodes=len(ready),
            failed=failed, awaiting_human=awaiting_human, progress=progress,
        )

    def tick(self, mission_id: str) -> MissionState:
        """Execute at most one ready node; persist; return the derived state."""
        mission, dag, statuses = self.store.load_mission(mission_id)
        done = {n for n, s in statuses.items() if s == DONE}
        ready = [n for n in dag.ready_nodes(done) if statuses.get(n) == PENDING]
        if not ready:
            state = self._derive(dag, statuses)
            self._commit_state(mission, state)
            return state

        node_id = ready[0]
        self.store.set_node_status(mission_id, node_id, RUNNING)
        self.store.append_event(mission_id, "node_start", {"node": node_id}, at=self.now())
        outcome = self.executor(mission_id, node_id)
        row = self.store.node_row(mission_id, node_id)
        attempts = int(row.get("attempts", 0)) + 1

        if outcome.ok:
            self.store.set_node_status(mission_id, node_id, DONE,
                                       attempts=attempts, evidence_ref=outcome.evidence_ref)
            self.store.append_event(mission_id, "node_done",
                                    {"node": node_id, "evidence_ref": outcome.evidence_ref}, at=self.now())
        else:
            if self.recovery.should_retry(attempts):
                self.store.set_node_status(mission_id, node_id, PENDING, attempts=attempts)
                self.store.append_event(mission_id, "node_retry",
                                        {"node": node_id, "attempts": attempts,
                                         "failure": outcome.failure_type}, at=self.now())
            else:
                self.store.set_node_status(mission_id, node_id, FAILED, attempts=attempts)
                self.store.append_event(mission_id, "node_failed",
                                        {"node": node_id, "attempts": attempts,
                                         "failure": outcome.failure_type}, at=self.now())

        _, _, statuses = self.store.load_mission(mission_id)
        state = self._derive(dag, statuses)
        self._commit_state(mission, state)
        return state

    def _commit_state(self, mission: Mission, state: MissionState) -> None:
        self.store.update_mission_state(mission.id, state, at=self.now())
        cp = Checkpoint(mission.id, mission.goal_key, mission.kanban_board_id, state, self.now())
        self.store.save_checkpoint(cp)

    def run(self, mission_id: str, *, max_ticks: int = 1000) -> MissionState:
        """Drive the mission to a terminal/blocked state (bounded — no infinite loop)."""
        state = MissionState.RUNNING
        for _ in range(max_ticks):
            state = self.tick(mission_id)
            if state in (MissionState.COMPLETED, MissionState.FAILED,
                         MissionState.CANCELLED, MissionState.WAITING_DEPENDENCY,
                         MissionState.WAITING_HUMAN, MissionState.BLOCKED):
                break
        return state

    def resume(self, mission_id: str, *, max_ticks: int = 1000) -> MissionState:
        """Reload from the store (post-restart) and continue. Idempotent: any node
        left in RUNNING from a crash is reset to PENDING before continuing."""
        _, dag, statuses = self.store.load_mission(mission_id)
        for nid, st in statuses.items():
            if st == RUNNING:
                self.store.set_node_status(mission_id, nid, PENDING)
                self.store.append_event(mission_id, "resume_reset_running", {"node": nid}, at=self.now())
        return self.run(mission_id, max_ticks=max_ticks)


__all__ = [
    "NodeOutcome", "NodeExecutor", "RecoveryPolicy",
    "WatchdogStatus", "WatchdogVerdict", "watchdog", "MissionRuntime",
    "PENDING", "RUNNING", "DONE", "FAILED", "BLOCKED",
]
