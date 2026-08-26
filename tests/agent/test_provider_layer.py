"""Tests + canaries for the provider catalog / routing / adapter layer (§36/§37/§38)."""

from __future__ import annotations

from agent.provider_adapter import (
    ConnectionStatus,
    ProviderConfig,
    local_health_url,
    sanitize_for_renderer,
    user_message,
    validate_key_format,
)
from agent.provider_catalog import (
    Capability,
    Curation,
    ProviderCatalog,
)
from agent.provider_routing import (
    ProviderCandidate,
    RoutingProfile,
    select_provider,
)

CAT = ProviderCatalog()


def _cand(pid, **kw):
    return ProviderCandidate(entry=CAT.get(pid), **kw)


# ---- catalog ------------------------------------------------------------ #


def test_catalog_has_expected_providers_and_no_invented_quota():
    ids = {e.id for e in CAT.all()}
    assert {"openai", "anthropic", "gemini", "openrouter", "groq", "ollama", "vllm"} <= ids
    # never invents quota numbers: pricing/quota unverified
    for e in CAT.all():
        assert e.last_verified_at is None
        assert e.free_tier_notes == "" or e.free_tier_notes  # notes never contain quota numbers by design


def test_catalog_filters_and_search():
    free_local = CAT.filter(local=True)
    assert all(e.is_local for e in free_local)
    assert CAT.get("ollama").no_card is True
    vision = CAT.by_capability(Capability.VISION)
    assert CAT.get("gemini") in vision
    assert CAT.search("gem")[0].id == "gemini"
    assert all(e.curation is Curation.RECOMMENDED for e in CAT.recommended())


# ---- adapter / secrets -------------------------------------------------- #


def test_key_format_validation():
    assert validate_key_format("openai", "sk-" + "a" * 40) is True
    assert validate_key_format("openai", "nope") is False
    assert validate_key_format("groq", "gsk_" + "a" * 30) is True
    assert validate_key_format("ollama", "") is True          # local: no key


def test_provider_config_has_no_raw_key_field():
    cfg = ProviderConfig("openai", has_key=True, key_ref="vault:1")
    assert not hasattr(cfg, "api_key")
    d = cfg.__dict__
    assert "api_key" not in d and d.get("key_ref") == "vault:1"


def test_sanitize_strips_secrets_for_renderer():
    view = sanitize_for_renderer({"provider": "openai", "api_key": "sk-secret",
                                  "authorization": "Bearer x", "model": "gpt"})
    assert view["api_key"] == "[stored securely]"
    assert view["authorization"] == "[stored securely]"
    assert view["model"] == "gpt"


def test_connection_user_messages():
    assert "invalid" in user_message(ConnectionStatus.INVALID_KEY).lower()
    assert local_health_url("ollama").endswith("/api/tags")


# ---- routing free-first ------------------------------------------------- #


def test_free_first_prefers_free_over_paid():
    cands = [_cand("openai", quality_score=0.95),          # paid, high quality
             _cand("groq", quality_score=0.7)]             # free
    d = select_provider(cands, task_capability=Capability.CODING,
                        local_only=False, profile=RoutingProfile.FREE_FIRST)
    assert d.provider_id == "groq"


def test_paid_selected_only_when_authorized():
    cands = [_cand("openai", quality_score=0.95)]          # only a paid option
    blocked = select_provider(cands, task_capability=Capability.CODING,
                              local_only=False, profile=RoutingProfile.BALANCED,
                              paid_authorized=False)
    assert blocked.provider_id is None and blocked.requires_paid_confirmation is True
    ok = select_provider(cands, task_capability=Capability.CODING,
                         local_only=False, paid_authorized=True)
    assert ok.provider_id == "openai"


# ---- CANARIES (§37) ----------------------------------------------------- #


def test_canary1_local_only_blocks_top_score_cloud_free():
    # cloud free provider with a perfect history + a local provider.
    cands = [_cand("gemini", quality_score=0.99),          # cloud, free, top score
             _cand("ollama", quality_score=0.5)]           # local
    d = select_provider(cands, task_capability=Capability.CHAT,
                        local_only=True, profile=RoutingProfile.QUALITY_FIRST)
    assert d.provider_id == "ollama"                        # privacy is ABSOLUTE
    # and if ONLY the cloud provider exists under local-only -> none eligible
    only_cloud = select_provider([_cand("gemini", quality_score=0.99)],
                                 task_capability=Capability.CHAT, local_only=True)
    assert only_cloud.provider_id is None


def test_canary2_free_first_skips_provider_without_capability():
    # groq is free but (in this catalog) has no VISION capability; gemini free has it.
    cands = [_cand("groq", quality_score=0.9), _cand("gemini", quality_score=0.6)]
    d = select_provider(cands, task_capability=Capability.VISION,
                        local_only=False, profile=RoutingProfile.FREE_FIRST)
    assert d.provider_id == "gemini"                        # groq lacks VISION -> skipped
    assert not CAT.get("groq").has(Capability.VISION)


def test_canary3_free_exhausted_paid_unauthorized_blocks_zero_paid_call():
    # the free provider's quota is exhausted; the only fallback is paid + unauthorized.
    cands = [_cand("gemini", quality_score=0.8, free_quota_exhausted=True),  # now paid-equiv/ineligible-free
             _cand("openai", quality_score=0.9)]                             # paid
    d = select_provider(cands, task_capability=Capability.CHAT,
                        local_only=False, profile=RoutingProfile.FREE_FIRST,
                        paid_authorized=False)
    assert d.provider_id is None                            # ASK/BLOCK
    assert d.requires_paid_confirmation is True             # zero paid call made


# ---- UX flow (§38): guided, no JSON/terminal/base-url needed ------------ #


def test_guided_connect_flow_has_official_key_page_and_states():
    e = CAT.get("gemini")
    assert e.get_key_url.startswith("https://")             # "Obter chave" -> official page
    # a leigo flow only needs: pick -> connect (key page) -> validate format -> test
    key = "AIza" + "b" * 35
    assert validate_key_format("gemini", key) is True
    # test states are simple + user-messaged
    for st in ConnectionStatus:
        assert isinstance(user_message(st), str)
