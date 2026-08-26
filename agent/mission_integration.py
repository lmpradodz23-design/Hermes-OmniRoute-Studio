"""Autonomy Kernel <-> OmniRoute mission composition (Prioridade 1 wiring, additive).

This is the single, ADDITIVE entry point a real host (gateway / goals / kanban / agent
loop) calls to run an intent as a real Mission through the existing MissionRuntime, with
per-node provider selection going through the existing OmniRoute path
(`route_for_mission` -> provider bridge -> real ProviderProfile -> transport) and every
outcome fed back into route_history / benchmark_arena, with mission_trace for observability.

It does NOT modify any mature runtime file and does NOT create a MissionV2 / router V2:
it composes the modules that already exist. The actual per-node work (calling the agent /
tool / provider transport) is injected via `do_work`, so the whole flow is unit-testable
in-process (no network, no GUI). The host supplies the real `do_work`, `registry`
(`providers/`), candidate builder (live health/quota/benchmark state), and a MissionStore.

Flow realized:
    USER INTENT -> Mission + MissionDag -> MissionRuntime.run()
        per node:  route_for_mission()  (free-first / LOCAL_ONLY absolute / ASK_BEFORE_PAID)
                   -> ResolvedProvider (real ProviderProfile) -> do_work(node, resolved)
                   -> NodeOutcome (+ evidence_ref) -> record_route_outcome() -> route_history
    -> checkpoint/resume + watchdog handled by MissionRuntime; trace correlates it all.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

from agent.mission import Mission
from agent.mission_dag import DagNode, MissionDag
from agent.mission_runtime import MissionRuntime, NodeOutcome
from agent.mission_store import MissionStore
from agent.mission_trace import MissionTrace
from agent.provider_catalog import Capability, ProviderCatalog
from agent.provider_routing import ProviderCandidate, RoutingProfile
from agent.provider_runtime_hooks import record_route_outcome, route_for_mission
from agent.provider_omniroute_bridge import ResolvedProvider
from agent.route_history import RouteHistory


# (node_id, resolved_or_None) -> (ok, evidence_ref, failure_type)
DoWork = Callable[[str, "ResolvedProvider | None"], "tuple[bool, str | None, str | None]"]


@dataclass(frozen=True)
class NodeSpec:
    """One mission node. `task_capability=None` marks a node that needs no provider."""

    node_id: str
    parents: tuple[str, ...] = ()
    task_capability: Capability | None = None
    task_type: str = "general"
    weight: float = 1.0
    label: str = ""


@dataclass
class ProviderContext:
    catalog: ProviderCatalog
    registry: object                                            # the real providers/ registry
    build_candidates: Callable[[Capability], Sequence[ProviderCandidate]]
    local_only: bool = False
    paid_authorized: bool = False
    profile: RoutingProfile = RoutingProfile.BALANCED
    key_refs: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class IntentResult:
    state: object                    # MissionState
    trace: MissionTrace
    history: RouteHistory


def provider_backed_executor(
    specs: Sequence[NodeSpec],
    ctx: ProviderContext,
    *,
    trace: MissionTrace,
    history: RouteHistory,
    now_fn: Callable[[], float],
    do_work: DoWork,
):
    """Build a NodeExecutor that routes each provider-needing node through OmniRoute
    (fail-closed), runs the real work via `do_work`, and records the outcome."""
    spec_by_id = {s.node_id: s for s in specs}

    def _exec(mission_id: str, node_id: str) -> NodeOutcome:
        spec = spec_by_id.get(node_id)
        resolved: ResolvedProvider | None = None

        if spec is not None and spec.task_capability is not None:
            out = route_for_mission(
                mission_id=mission_id, node_id=node_id, run_id=mission_id, at=now_fn(),
                catalog=ctx.catalog, registry=ctx.registry,
                candidates=list(ctx.build_candidates(spec.task_capability)),
                task_capability=spec.task_capability, local_only=ctx.local_only,
                profile=ctx.profile, paid_authorized=ctx.paid_authorized,
                key_refs=ctx.key_refs, trace=trace,
            )
            if not out.ok:
                # fail CLOSED: no provider / ask-before-paid / local-only violation.
                # do_work is NEVER called -> zero paid work, zero cloud egress on LOCAL_ONLY.
                record_route_outcome(history, task_type=spec.task_type, model="none",
                                     provider="none", success=False,
                                     failure_type=out.outcome.reason, local_only=ctx.local_only)
                return NodeOutcome(False, evidence_ref=None, failure_type=out.outcome.reason)
            resolved = out.outcome.resolved

        ok, evidence_ref, failure_type = do_work(node_id, resolved)

        if resolved is not None and spec is not None:
            record_route_outcome(
                history, task_type=spec.task_type, model=resolved.provider_id,
                provider=resolved.provider_id, success=ok,
                verification_score=1.0 if ok else 0.0,
                failure_type=failure_type, local_only=ctx.local_only,
            )
        return NodeOutcome(ok, evidence_ref=evidence_ref, failure_type=failure_type)

    return _exec


def build_dag(specs: Sequence[NodeSpec]) -> MissionDag:
    return MissionDag([DagNode(s.node_id, s.parents, s.weight, s.label) for s in specs])


def run_intent_as_mission(
    *,
    store: MissionStore,
    mission: Mission,
    specs: Sequence[NodeSpec],
    ctx: ProviderContext,
    do_work: DoWork,
    now_fn: Callable[[], float],
    trace: MissionTrace | None = None,
    history: RouteHistory | None = None,
    max_ticks: int = 1000,
) -> IntentResult:
    """Run an intent as a real Mission end-to-end through the existing MissionRuntime."""
    trace = trace or MissionTrace()
    history = history or RouteHistory()
    dag = build_dag(specs)
    runtime = MissionRuntime(
        store,
        provider_backed_executor(specs, ctx, trace=trace, history=history,
                                 now_fn=now_fn, do_work=do_work),
        now_fn=now_fn,
    )
    runtime.create(mission, dag)
    state = runtime.run(mission.id, max_ticks=max_ticks)
    return IntentResult(state=state, trace=trace, history=history)


__all__ = [
    "NodeSpec", "ProviderContext", "IntentResult",
    "DoWork", "provider_backed_executor", "build_dag", "run_intent_as_mission",
]
