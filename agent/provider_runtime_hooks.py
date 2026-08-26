"""Provider layer <-> Autonomy Kernel hooks (§7/§8/§9 wiring).

Ties the provider selection layer into the EXISTING kernel primitives, closing the
learning loop without recreating any of them:
  - route_history: record each real provider outcome (RouteRecord);
  - benchmark_arena: turn that history into per-model composite quality scores that
    feed back into `build_candidates(quality=...)` (the Benchmark Arena -> routing hook);
  - mission_trace: emit a redaction-safe TraceEvent for every routing decision;
  - mission_evidence: produce an EvidenceItem proving the chosen provider was reachable;
  - provider_omniroute_bridge: `route_for_mission()` is the single integrated entry point
    a mission-node dispatch calls to route + resolve + trace in one step.

Pure module. Timestamps are INJECTED (`at`) so it is deterministic and testable — no
wall-clock, matching the kernel's "pass timestamps in" rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from agent.benchmark_arena import score as arena_score
from agent.mission_evidence import EvidenceItem, EvidenceKind
from agent.mission_trace import MissionTrace, TraceEvent
from agent.provider_catalog import Capability, ProviderCatalog
from agent.provider_omniroute_bridge import (
    BridgeOutcome,
    ResolvedProvider,
    route_and_resolve,
)
from agent.provider_routing import ProviderCandidate, RoutingProfile
from agent.route_history import RouteHistory, RouteRecord


# ---- item 7/8: record outcomes + benchmark-arena quality feedback ------- #

def record_route_outcome(
    history: RouteHistory,
    *,
    task_type: str,
    model: str,
    provider: str,
    success: bool,
    verification_score: float = 0.0,
    latency_ms: float = 0.0,
    cost_usd: float = 0.0,
    retries: int = 0,
    failure_type: str | None = None,
    local_only: bool = False,
) -> RouteRecord:
    """Append a real provider outcome to route_history (feeds the benchmark arena)."""
    rec = RouteRecord(
        task_type=task_type,
        model=model,
        provider=provider,
        success=success,
        verification_score=verification_score,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        retries=retries,
        failure_type=failure_type,
        privacy_policy="local_only" if local_only else "any",
    )
    history.record(rec)
    return rec


def quality_scores(history: RouteHistory, task_type: str,
                   models: Sequence[str]) -> dict[str, float]:
    """Benchmark Arena -> routing hook: composite quality per model, to feed
    `build_candidates(quality=...)`. Models with no history are omitted (caller keeps
    the neutral prior). Composite is clamped into [0,1] for the router's expectations."""
    out: dict[str, float] = {}
    for m in models:
        recs = history.for_key(task_type, m)          # records already filtered by (task_type, model)
        bs = arena_score(recs, task_type, m)
        if bs is not None:
            out[m] = max(0.0, min(1.0, bs.composite))
    return out


# ---- item 7: evidence hook --------------------------------------------- #

def route_evidence_item(resolved: ResolvedProvider | None, *, reachable: bool) -> EvidenceItem:
    """Evidence that the routed provider was actually reachable (bound to a real check).
    `ref` is a non-secret pointer (provider id), never a key."""
    pid = resolved.provider_id if resolved is not None else "none"
    return EvidenceItem(kind=EvidenceKind.COMMAND_RESULT, ref=f"provider_reachable:{pid}", ok=reachable)


# ---- item 9: mission / OmniRoute routing integration -------------------- #

@dataclass(frozen=True)
class MissionRouteOutcome:
    outcome: BridgeOutcome
    trace_event: TraceEvent

    @property
    def ok(self) -> bool:
        return self.outcome.ok


def route_for_mission(
    *,
    mission_id: str,
    node_id: str,
    run_id: str | None,
    at: float,
    catalog: ProviderCatalog,
    registry,
    candidates: Sequence[ProviderCandidate],
    task_capability: Capability,
    local_only: bool,
    profile: RoutingProfile = RoutingProfile.BALANCED,
    paid_authorized: bool = False,
    key_refs: Mapping[str, str] | None = None,
    trace: MissionTrace | None = None,
) -> MissionRouteOutcome:
    """Single integrated entry point for a mission node: route + resolve the REAL
    provider and emit a correlated, redaction-safe trace event."""
    outcome = route_and_resolve(
        catalog=catalog, registry=registry, candidates=candidates,
        task_capability=task_capability, local_only=local_only,
        profile=profile, paid_authorized=paid_authorized, key_refs=key_refs,
    )
    if outcome.ok:
        status, failure = "routed", None
        provider = outcome.resolved.provider_id
    elif outcome.requires_paid_confirmation:
        status, failure, provider = "ask_before_paid", outcome.reason, None
    else:
        status, failure, provider = "no_provider", outcome.reason, None

    ev = TraceEvent(
        mission_id=mission_id, kind="model_route", at=at, node_id=node_id,
        run_id=run_id, provider=provider, status=status, failure_type=failure,
    )
    if trace is not None:
        trace.append(ev)
    return MissionRouteOutcome(outcome, ev)


__all__ = [
    "record_route_outcome", "quality_scores", "route_evidence_item",
    "MissionRouteOutcome", "route_for_mission",
]
