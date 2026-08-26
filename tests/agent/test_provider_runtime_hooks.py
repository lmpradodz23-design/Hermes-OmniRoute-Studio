"""Contract tests for provider <-> kernel hooks (§7/§8/§9): evidence, arena, mission routing."""

from __future__ import annotations

from dataclasses import dataclass, field

from agent.mission_trace import MissionTrace
from agent.provider_catalog import Capability, ProviderCatalog
from agent.provider_omniroute_bridge import build_candidates
from agent.provider_routing import RoutingProfile
from agent.provider_runtime_hooks import (
    quality_scores,
    record_route_outcome,
    route_evidence_item,
    route_for_mission,
)
from agent.route_history import RouteHistory

CAT = ProviderCatalog()


@dataclass
class FakeProfile:
    name: str
    aliases: tuple = ()
    base_url: str = ""
    signup_url: str = ""
    supports_vision: bool = True


@dataclass
class FakeRegistry:
    profiles: list = field(default_factory=list)

    def get_provider_profile(self, name):
        for p in self.profiles:
            if p.name == name or name in p.aliases:
                return p
        return None

    def list_providers(self):
        return self.profiles


# ---- item 7/8: history + arena ----------------------------------------- #

def test_record_route_outcome_sets_privacy_and_appends():
    h = RouteHistory()
    rec = record_route_outcome(h, task_type="chat", model="groq", provider="groq",
                               success=True, verification_score=1.0, local_only=True)
    assert rec.privacy_policy == "local_only"
    assert len(h) == 1


def test_quality_scores_from_history():
    h = RouteHistory()
    for _ in range(3):
        record_route_outcome(h, task_type="chat", model="groq", provider="groq",
                             success=True, verification_score=1.0)
    for _ in range(2):
        record_route_outcome(h, task_type="chat", model="openai", provider="openai",
                             success=False, verification_score=0.0)
    scores = quality_scores(h, "chat", ["groq", "openai", "gemini"])
    assert scores["groq"] > scores["openai"]        # good history ranks higher
    assert "gemini" not in scores                    # no history -> omitted (neutral prior kept)
    assert 0.0 <= scores["groq"] <= 1.0


# ---- item 7: evidence hook --------------------------------------------- #

def test_route_evidence_item_reachable_flag_and_no_secret():
    from agent.provider_omniroute_bridge import ResolvedProvider
    from agent.provider_adapter import ProviderConfig
    rp = ResolvedProvider("groq", object(), "https://x", ProviderConfig("groq"), "resolved", False)
    ok = route_evidence_item(rp, reachable=True)
    assert ok.ok is True and "groq" in ok.ref and "key" not in ok.ref.lower()
    bad = route_evidence_item(None, reachable=False)
    assert bad.ok is False and "none" in bad.ref


# ---- item 9: mission routing integration ------------------------------- #

def test_route_for_mission_success_traces_event():
    reg = FakeRegistry([FakeProfile("groq")])
    cands = build_candidates(CAT, configured={"groq": True}, include=["groq"])
    trace = MissionTrace()
    out = route_for_mission(mission_id="m1", node_id="n1", run_id="r1", at=1000.0,
                            catalog=CAT, registry=reg, candidates=cands,
                            task_capability=Capability.CODING, local_only=False,
                            profile=RoutingProfile.FREE_FIRST, key_refs={"groq": "vault:g"},
                            trace=trace)
    assert out.ok and out.trace_event.status == "routed"
    assert out.trace_event.provider == "groq" and out.trace_event.kind == "model_route"
    assert trace.timeline("m1")                       # event was appended + correlated


def test_route_for_mission_local_only_blocks_cloud():
    reg = FakeRegistry([FakeProfile("gemini")])
    cands = build_candidates(CAT, configured={"gemini": True}, include=["gemini"])
    out = route_for_mission(mission_id="m1", node_id="n1", run_id="r1", at=1.0,
                            catalog=CAT, registry=reg, candidates=cands,
                            task_capability=Capability.CHAT, local_only=True)
    assert not out.ok and out.trace_event.status == "no_provider"


def test_route_for_mission_paid_unauthorized_asks():
    reg = FakeRegistry([FakeProfile("openai")])
    cands = build_candidates(CAT, configured={"openai": True}, include=["openai"])
    out = route_for_mission(mission_id="m1", node_id="n1", run_id="r1", at=1.0,
                            catalog=CAT, registry=reg, candidates=cands,
                            task_capability=Capability.CODING, local_only=False,
                            paid_authorized=False)
    assert not out.ok and out.outcome.requires_paid_confirmation
    assert out.trace_event.status == "ask_before_paid"


# ---- closed loop: arena quality feeds candidate build ------------------ #

def test_arena_quality_feeds_candidate_scores():
    h = RouteHistory()
    for _ in range(4):
        record_route_outcome(h, task_type="chat", model="groq", provider="groq",
                             success=True, verification_score=1.0)
    q = quality_scores(h, "chat", [e.id for e in CAT.all()])
    cands = build_candidates(CAT, configured={"groq": True}, quality=q, include=["groq"])
    groq = next(c for c in cands if c.entry.id == "groq")
    assert groq.quality_score == q["groq"] > 0.6      # learned score overrides neutral prior
