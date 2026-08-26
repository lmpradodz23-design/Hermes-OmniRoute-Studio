"""Tests for catalog<->registry reconciliation and the Settings view-model (§38/§39)."""

from __future__ import annotations

from dataclasses import dataclass, field

from agent.provider_adapter import ConnectionStatus
from agent.provider_catalog import ProviderCatalog
from agent.provider_catalog_link import reconcile
from agent.provider_settings_view import build_settings_view

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

    def list_providers(self):
        return self.profiles

    def get_provider_profile(self, name):
        for p in self.profiles:
            if p.name == name or name in p.aliases:
                return p
        return None


# ---- reconciliation (anti-parallel guard) ------------------------------- #

def test_reconcile_registry_wins_for_runtime_facts_and_flags_gaps():
    reg = FakeRegistry([
        FakeProfile("gemini", base_url="https://gen.example/v1",
                    signup_url="https://keys.example/gemini", supports_vision=True),
        FakeProfile("openai", base_url="https://api.openai.com/v1", supports_vision=True),
        # a runtime provider with NO catalog curation entry:
        FakeProfile("some-oss-proxy", base_url="http://x"),
    ])
    rec = reconcile(CAT, reg)

    gem = rec.get("gemini")
    assert gem.has_runtime_profile is True and gem.is_executable is True
    assert gem.api_base == "https://gen.example/v1"          # registry base_url wins
    assert gem.get_key_url == "https://keys.example/gemini"   # registry signup_url wins

    # cloud provider with no runtime profile is not executable and is reported
    assert "anthropic" in rec.catalog_without_runtime
    anthropic = rec.get("anthropic")
    assert anthropic.has_runtime_profile is False and anthropic.is_executable is False

    # local providers are executable without a registry profile
    assert rec.get("ollama").is_executable is True

    # a runtime provider missing curation metadata is surfaced (not hidden)
    assert "some-oss-proxy" in rec.registry_without_catalog


def test_reconcile_detects_capability_drift_instead_of_lying():
    reg = FakeRegistry([FakeProfile("gemini", supports_vision=False)])  # contradicts catalog VISION
    rec = reconcile(CAT, reg)
    gem = rec.get("gemini")
    assert any("VISION" in d for d in gem.drift)


def test_reconcile_alias_match():
    reg = FakeRegistry([FakeProfile("google", aliases=("gemini",), base_url="http://g")])
    rec = reconcile(CAT, reg)
    assert rec.get("gemini").has_runtime_profile is True


# ---- settings view (lay-user surface) ----------------------------------- #

def test_view_is_secret_safe_and_has_sections():
    view = build_settings_view(CAT, configured={"gemini": True})
    cards = view.all_cards()
    assert cards
    for c in cards:
        # the frozen ProviderCard has no secret-bearing field at all
        for fname in c.__dict__:
            assert not any(m in fname.lower()
                           for m in ("key", "token", "secret", "password", "credential")) or fname in ("get_key_url", "has_key", "needs_key")
    # has_key surfaced as a boolean, never a raw key value
    gem = next(c for c in cards if c.id == "gemini")
    assert gem.has_key is True
    assert isinstance(gem.has_key, bool)


def test_view_guided_flow_cloud_vs_local():
    view = build_settings_view(CAT)
    gem = next(c for c in view.all_cards() if c.id == "gemini")
    assert gem.needs_key is True
    assert gem.guided_steps[0].href.startswith("https://")   # official key page
    assert "key" in gem.guided_steps[0].title.lower()

    oll = next(c for c in view.all_cards() if c.id == "ollama")
    assert oll.needs_key is False
    assert any("Detect" in s.title or "detect" in s.detail.lower() for s in oll.guided_steps)


def test_view_local_only_marks_cloud_ineligible():
    view = build_settings_view(CAT, executable={"gemini": True}, local_only=True)
    gem = next(c for c in view.all_cards() if c.id == "gemini")
    oll = next(c for c in view.all_cards() if c.id == "ollama")
    assert gem.executable is False        # LOCAL_ONLY: cloud ineligible even if a profile exists
    assert oll.executable is True


def test_view_quick_start_prefers_connected_local_then_free_nocard():
    # a local provider already connected -> quick start picks it
    v1 = build_settings_view(CAT, statuses={"ollama": ConnectionStatus.CONNECTED})
    assert v1.quick_start_provider_id == "ollama"

    # nothing connected, cloud allowed -> a free, no-card, recommended cloud option
    v2 = build_settings_view(CAT)
    e = CAT.get(v2.quick_start_provider_id)
    assert e is not None and not e.is_local
    from agent.provider_catalog import Tri
    assert e.free_tier == Tri.YES and e.no_card is True


def test_view_status_never_fakes_connected():
    view = build_settings_view(CAT)   # no statuses injected
    for c in view.all_cards():
        assert c.connected is False
        assert c.status in {"UNKNOWN"}          # absent probe -> UNKNOWN, never CONNECTED
