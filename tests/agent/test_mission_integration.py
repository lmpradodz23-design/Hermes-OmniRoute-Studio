"""Source-integration test: Autonomy Kernel + OmniRoute composed end-to-end.

Runs a real Mission through the real MissionRuntime + MissionStore (SQLite), with each
provider-needing node routed through the real OmniRoute path (route_for_mission), and
every outcome recorded to route_history. Proves the integrated flow, the fail-closed
guards (ASK_BEFORE_PAID, LOCAL_ONLY), and durable checkpoint/resume — with NO network
and NO GUI. Runtime (Electron/build/install/E2E) is validated only on the host.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent.mission import Mission, MissionState
from agent.mission_integration import (
    NodeSpec,
    ProviderContext,
    provider_backed_executor,
    run_intent_as_mission,
)
from agent.mission_runtime import MissionRuntime
from agent.mission_store import MissionStore
from agent.mission_trace import MissionTrace
from agent.provider_catalog import Capability, ProviderCatalog
from agent.provider_omniroute_bridge import build_candidates
from agent.route_history import RouteHistory

CAT = ProviderCatalog()


@dataclass
class FakeProfile:
    name: str
    aliases: tuple = ()
    base_url: str = "https://x/v1"
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


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        self.t += 1.0
        return self.t


class WorkSpy:
    def __init__(self, ok=True):
        self.calls = []
        self.ok = ok

    def __call__(self, node_id, resolved):
        self.calls.append((node_id, getattr(resolved, "provider_id", None)))
        return (self.ok, f"ev:{node_id}", None if self.ok else "boom")


def _candidates_for(providers, configured):
    def _b(cap):
        return build_candidates(CAT, configured=configured, include=providers)
    return _b


# ---- 1. happy path: local provider node + downstream node completes ---- #

def test_intent_completes_with_local_provider_and_records_history(tmp_path):
    store = MissionStore(tmp_path / "m.db")
    specs = [
        NodeSpec("route", task_capability=Capability.CHAT, task_type="chat"),
        NodeSpec("finish", parents=("route",)),          # non-provider node
    ]
    ctx = ProviderContext(
        catalog=CAT, registry=FakeRegistry([]),           # local needs no profile
        build_candidates=_candidates_for(["ollama"], {"ollama": True}),
        local_only=False,
    )
    work = WorkSpy(ok=True)
    res = run_intent_as_mission(
        store=store, mission=Mission(id="m1", title="do X", state=MissionState.DRAFT),
        specs=specs, ctx=ctx, do_work=work, now_fn=Clock(),
    )
    assert res.state is MissionState.COMPLETED
    assert ("route", "ollama") in work.calls and ("finish", None) in work.calls
    assert len(res.history) == 1                          # the routed node was recorded
    assert res.trace.timeline("m1")                       # correlated events exist


# ---- 2. ASK_BEFORE_PAID: paid-unauthorized node fails closed ----------- #

def test_paid_unauthorized_node_fails_closed_zero_work(tmp_path):
    store = MissionStore(tmp_path / "m.db")
    specs = [NodeSpec("route", task_capability=Capability.CODING, task_type="code")]
    ctx = ProviderContext(
        catalog=CAT, registry=FakeRegistry([FakeProfile("openai")]),
        build_candidates=_candidates_for(["openai"], {"openai": True}),  # paid only
        paid_authorized=False,
    )
    work = WorkSpy(ok=True)
    res = run_intent_as_mission(
        store=store, mission=Mission(id="m2", title="code", state=MissionState.DRAFT),
        specs=specs, ctx=ctx, do_work=work, now_fn=Clock(),
    )
    assert res.state is MissionState.FAILED
    assert work.calls == []                               # do_work NEVER ran -> zero paid work


# ---- 3. LOCAL_ONLY: cloud node fails closed, zero egress --------------- #

def test_local_only_cloud_node_fails_closed(tmp_path):
    store = MissionStore(tmp_path / "m.db")
    specs = [NodeSpec("route", task_capability=Capability.CHAT, task_type="chat")]
    ctx = ProviderContext(
        catalog=CAT, registry=FakeRegistry([FakeProfile("gemini")]),
        build_candidates=_candidates_for(["gemini"], {"gemini": True}),  # cloud only
        local_only=True, paid_authorized=True,
    )
    work = WorkSpy(ok=True)
    res = run_intent_as_mission(
        store=store, mission=Mission(id="m3", title="chat", state=MissionState.DRAFT),
        specs=specs, ctx=ctx, do_work=work, now_fn=Clock(),
    )
    assert res.state is MissionState.FAILED
    assert work.calls == []                               # no cloud work under LOCAL_ONLY


# ---- 4. durable checkpoint/resume (state lives in the store) ----------- #

def test_checkpoint_resume_from_store(tmp_path):
    store = MissionStore(tmp_path / "m.db")
    specs = [
        NodeSpec("route", task_capability=Capability.CHAT, task_type="chat"),
        NodeSpec("finish", parents=("route",)),
    ]
    ctx = ProviderContext(
        catalog=CAT, registry=FakeRegistry([]),
        build_candidates=_candidates_for(["ollama"], {"ollama": True}),
    )
    clock = Clock()
    trace, history = MissionTrace(), RouteHistory()

    def _runtime():
        return MissionRuntime(
            store,
            provider_backed_executor(specs, ctx, trace=trace, history=history,
                                     now_fn=clock, do_work=WorkSpy(ok=True)),
            now_fn=clock,
        )

    from agent.mission_integration import build_dag
    rt1 = _runtime()
    rt1.create(Mission(id="m4", title="resume", state=MissionState.DRAFT), build_dag(specs))
    rt1.tick("m4")                                        # execute one node, then "crash"

    # brand-new runtime instance on the SAME store -> resume finishes it
    rt2 = _runtime()
    final = rt2.resume("m4")
    assert final is MissionState.COMPLETED               # state was durable, not in memory
