"""Contract tests for the Provider Catalog -> OmniRoute REAL bridge (§1-43 wiring)."""

from __future__ import annotations

from dataclasses import dataclass, field

from agent.provider_catalog import Capability, ProviderCatalog
from agent.provider_omniroute_bridge import (
    build_candidates,
    route_and_resolve,
)
from agent.provider_routing import RoutingProfile

CAT = ProviderCatalog()


# ---- fake OmniRoute registry (duck-typed like providers/__init__.py) ---- #

@dataclass
class FakeProfile:
    name: str
    aliases: tuple = ()
    base_url: str = ""
    signup_url: str = ""
    supports_vision: bool = False


@dataclass
class FakeRegistry:
    profiles: list = field(default_factory=list)

    def get_provider_profile(self, name):
        # resolves name + alias, like the real registry
        for p in self.profiles:
            if p.name == name or name in p.aliases:
                return p
        return None

    def list_providers(self):
        return self.profiles


def _reg(*names_with_vision):
    profs = []
    for spec in names_with_vision:
        if isinstance(spec, tuple):
            nm, vis = spec
        else:
            nm, vis = spec, False
        profs.append(FakeProfile(nm, base_url=f"https://api.{nm}.example/v1",
                                 signup_url=f"https://{nm}.example/keys", supports_vision=vis))
    return FakeRegistry(profs)


# ---- 1. provider conhecido --------------------------------------------- #

def test_1_known_provider_resolves_real_profile():
    reg = _reg(("groq", False))
    cands = build_candidates(CAT, configured={"groq": True}, include=["groq"])
    out = route_and_resolve(catalog=CAT, registry=reg, candidates=cands,
                            task_capability=Capability.CODING, local_only=False,
                            profile=RoutingProfile.FREE_FIRST, key_refs={"groq": "vault:groq"})
    assert out.ok and out.resolved.provider_id == "groq"
    assert out.resolved.profile is reg.profiles[0]           # the REAL existing profile, not a copy
    assert out.resolved.api_base == "https://api.groq.example/v1"   # registry base_url wins
    assert out.resolved.config.key_ref == "vault:groq"


# ---- 2. provider inexistente (no runtime profile) ---------------------- #

def test_2_unknown_provider_fails_closed():
    reg = FakeRegistry([])                                   # cloud provider has NO profile
    cands = build_candidates(CAT, configured={"groq": True}, include=["groq"])
    out = route_and_resolve(catalog=CAT, registry=reg, candidates=cands,
                            task_capability=Capability.CODING, local_only=False,
                            profile=RoutingProfile.FREE_FIRST)
    assert not out.ok
    assert out.reason.startswith("unknown_provider")


# ---- 3. capability ausente --------------------------------------------- #

def test_3_missing_capability_fails_closed():
    reg = _reg(("groq", False))
    cands = build_candidates(CAT, configured={"groq": True}, include=["groq"])
    # groq has no VISION capability in the catalog
    out = route_and_resolve(catalog=CAT, registry=reg, candidates=cands,
                            task_capability=Capability.VISION, local_only=False,
                            profile=RoutingProfile.FREE_FIRST)
    assert not out.ok
    # either the router finds nothing eligible, or the bridge's own guard trips — both fail closed
    assert ("capability" in out.reason) or ("no_eligible" in out.reason)


# ---- 4. LOCAL_ONLY + cloud --------------------------------------------- #

def test_4_local_only_blocks_cloud_and_picks_local():
    reg = _reg(("gemini", True))                             # only a cloud profile exists
    cands = build_candidates(CAT, configured={"gemini": True},
                             include=["gemini", "ollama"])   # ollama is local
    out = route_and_resolve(catalog=CAT, registry=reg, candidates=cands,
                            task_capability=Capability.CHAT, local_only=True,
                            profile=RoutingProfile.QUALITY_FIRST)
    assert out.ok and out.resolved.provider_id == "ollama"   # privacy absolute -> local
    assert out.resolved.is_local is True

    # and with ONLY a cloud candidate under local_only -> fail closed
    only_cloud = build_candidates(CAT, configured={"gemini": True}, include=["gemini"])
    out2 = route_and_resolve(catalog=CAT, registry=reg, candidates=only_cloud,
                             task_capability=Capability.CHAT, local_only=True)
    assert not out2.ok


# ---- 5. paid fallback não autorizado ----------------------------------- #

def test_5_paid_unauthorized_requires_confirmation_zero_resolve():
    reg = _reg(("openai", True))                             # openai is paid (free_tier=NO)
    cands = build_candidates(CAT, configured={"openai": True}, include=["openai"])
    out = route_and_resolve(catalog=CAT, registry=reg, candidates=cands,
                            task_capability=Capability.CODING, local_only=False,
                            profile=RoutingProfile.BALANCED, paid_authorized=False)
    assert not out.ok
    assert out.requires_paid_confirmation is True            # ASK_BEFORE_PAID, no provider resolved
    # authorized -> resolves
    ok = route_and_resolve(catalog=CAT, registry=reg, candidates=cands,
                           task_capability=Capability.CODING, local_only=False,
                           paid_authorized=True)
    assert ok.ok and ok.resolved.provider_id == "openai"


# ---- 6. capability drift (catalog vs runtime) -------------------------- #

def test_6_capability_drift_is_flagged_not_hidden():
    # catalog says gemini has VISION; runtime profile denies it -> drift surfaced, not asserted as truth.
    reg = _reg(("gemini", False))                            # supports_vision=False contradicts catalog
    cands = build_candidates(CAT, configured={"gemini": True}, include=["gemini"])
    out = route_and_resolve(catalog=CAT, registry=reg, candidates=cands,
                            task_capability=Capability.CHAT, local_only=False,
                            profile=RoutingProfile.QUALITY_FIRST, paid_authorized=True,
                            key_refs={"gemini": "vault:gem"})
    assert out.ok
    assert any("VISION" in d for d in out.resolved.drift)


# ---- 7. secret never appears in the sanitized object ------------------- #

def test_7_no_secret_in_sanitized_view():
    reg = _reg(("gemini", True))
    cands = build_candidates(CAT, configured={"gemini": True}, include=["gemini"])
    out = route_and_resolve(catalog=CAT, registry=reg, candidates=cands,
                            task_capability=Capability.CHAT, local_only=False,
                            paid_authorized=True, key_refs={"gemini": "vault:gem"})
    view = out.sanitized_view()
    flat = repr(view).lower()
    # renderer view carries NO api_key and NOT even the key_ref handle — only a boolean.
    assert "api_key" not in flat
    assert "vault:gem" not in flat            # the ref never reaches the renderer view
    assert "key_ref" not in view["config"]
    assert view["config"]["configured"] is True
    # and the internal ProviderConfig has no raw-secret field at all
    assert not hasattr(out.resolved.config, "api_key")
    # the key_ref stays available on the internal config (for the transport/secret_sources)
    assert out.resolved.config.key_ref == "vault:gem"
