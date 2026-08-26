"""Self-healing loop (Wave 6, §56/§57).

A health signal (from doctor / gateway / watchdog) seeds an INTERNAL mission that
reproduces the fault, finds root cause, patches IN ISOLATION (worktree/sandbox),
runs tests + a security review, and produces an INTEGRATION PROPOSAL — it NEVER
modifies the active installation directly (separation of powers: propose ->
independent review -> integration gate). Composes the existing kernel
(mission_dag + mission_runtime) and skill_lifecycle.ImprovementProposal; pure
orchestration, unit-testable with fakes.
"""

from __future__ import annotations

from dataclasses import dataclass

from agent.mission import Mission, MissionState
from agent.mission_dag import DagNode, MissionDag
from agent.mission_runtime import MissionRuntime, NodeExecutor
from agent.mission_store import MissionStore
from agent.safe_repair import Health
from agent.skill_lifecycle import ImprovementProposal


# The self-heal pipeline nodes. Note there is NO "apply_to_production" node:
# the terminal node only PROPOSES an integration.
NODES = ("reproduce", "root_cause", "patch_isolated", "test", "security_review", "propose")


@dataclass(frozen=True)
class HealthSignal:
    component: str
    health: Health
    detail: str = ""
    evidence_ref: str | None = None


def should_heal(signal: HealthSignal) -> bool:
    """Only a FAIL triggers a heal mission. OK/WARN don't; BLOCKED is not auto-fixable."""
    return signal.health == Health.FAIL


def build_self_heal_dag() -> MissionDag:
    return MissionDag([
        DagNode("reproduce", weight=2.0, label="Reproduce fault"),
        DagNode("root_cause", parents=("reproduce",), weight=2.0, label="Find root cause"),
        DagNode("patch_isolated", parents=("root_cause",), weight=3.0,
                label="Patch in isolated worktree"),
        DagNode("test", parents=("patch_isolated",), weight=2.0, label="Run tests"),
        DagNode("security_review", parents=("patch_isolated",), weight=1.0,
                label="Security review"),
        DagNode("propose", parents=("test", "security_review"), weight=1.0,
                label="Integration proposal (never auto-apply)"),
    ])


@dataclass(frozen=True)
class SelfHealResult:
    state: MissionState
    proposal: ImprovementProposal | None   # PROPOSED (never INTEGRATED) on success


def run_self_heal(
    store: MissionStore,
    signal: HealthSignal,
    executor: NodeExecutor,
    *,
    now_fn,
    mission_id: str | None = None,
    max_attempts: int = 2,
) -> SelfHealResult:
    """Run the isolated self-heal mission. Returns a PROPOSAL on success — the
    active install is never modified here."""
    if not should_heal(signal):
        return SelfHealResult(MissionState.CANCELLED, None)

    mid = mission_id or f"heal-{signal.component}"
    from agent.mission_runtime import RecoveryPolicy

    rt = MissionRuntime(store, executor, now_fn=now_fn, recovery=RecoveryPolicy(max_attempts))
    rt.create(Mission(id=mid, title=f"self-heal {signal.component}",
                      meta={"health": signal.health.value, "component": signal.component}),
              build_self_heal_dag())
    state = rt.run(mid)

    proposal = None
    if state == MissionState.COMPLETED:
        proposal = ImprovementProposal(
            id=f"heal-prop-{signal.component}",
            target_skill=signal.component,
            rationale=f"self-heal for {signal.component}: {signal.detail}",
            diff_ref=f"worktree:heal/{signal.component}",
        )   # PROPOSED — requires independent review before integration
    return SelfHealResult(state, proposal)


__all__ = ["HealthSignal", "SelfHealResult", "should_heal", "build_self_heal_dag", "run_self_heal", "NODES"]
