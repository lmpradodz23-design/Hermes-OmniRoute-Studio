"""LOCAL_ONLY — account-usage fetch must not egress under local-only.

Every account-usage endpoint is a remote SaaS (api.anthropic.com, chatgpt.com,
openrouter) with no loopback form, so under local-only the fetch is suppressed
entirely rather than shipping account metadata off-machine.
"""

import agent.account_usage as au


def test_fetch_suppressed_under_local_only(monkeypatch):
    import agent.local_only as lo

    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)

    called = {"n": 0}

    def _boom(*a, **k):
        called["n"] += 1
        raise AssertionError("must not fetch under local-only")

    monkeypatch.setattr(au, "_fetch_anthropic_account_usage", _boom)
    monkeypatch.setattr(au, "_fetch_codex_account_usage", _boom)
    monkeypatch.setattr(au, "_fetch_openrouter_account_usage", _boom)

    assert au.fetch_account_usage("anthropic") is None
    assert au.fetch_account_usage("openai-codex") is None
    assert au.fetch_account_usage("openrouter") is None
    assert called["n"] == 0


def test_fetch_runs_when_local_only_off(monkeypatch):
    import agent.local_only as lo

    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: False)

    sentinel = object()
    monkeypatch.setattr(au, "_fetch_anthropic_account_usage", lambda: sentinel)
    assert au.fetch_account_usage("anthropic") is sentinel


def test_nous_portal_no_remote_fetch_under_local_only(monkeypatch):
    # /usage and /topup fetch Nous portal account info with force_fresh=True,
    # a remote GET to portal.nousresearch.com. Under local-only, the fresh
    # remote fetch (and the pool remote fallbacks) must never fire.
    import agent.local_only as lo
    import hermes_cli.nous_account as na

    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)

    def _boom(*a, **k):
        raise AssertionError("must not fetch the portal under local-only")

    import hermes_cli.auth as auth

    monkeypatch.setattr(na, "_fresh_account_info", _boom)
    monkeypatch.setattr(na, "_info_from_oauth_pool", _boom)
    monkeypatch.setattr(na, "_info_from_inference_key_pool", _boom)
    monkeypatch.setattr(
        auth, "get_provider_auth_state",
        lambda p: {"access_token": "tok", "portal_base_url": "https://portal.nousresearch.com"},
        raising=False,
    )
    # Expired/undecodable JWT → no local snapshot → degraded state, still NO egress.
    monkeypatch.setattr(na, "_info_from_valid_jwt", lambda *a, **k: None)

    info = na.get_nous_portal_account_info(force_fresh=True)
    assert info.fresh is False
    # Also with no token at all: no pool remote fallback under local-only.
    monkeypatch.setattr(auth, "get_provider_auth_state", lambda p: {}, raising=False)
    info2 = na.get_nous_portal_account_info(force_fresh=True)
    assert info2.logged_in is False and info2.source == "none"


def test_reset_credit_suppressed_under_local_only(monkeypatch):
    # /usage reset does a remote GET + POST to the Codex backend — it must not
    # fire under local-only (must not even resolve credentials / open a client).
    import agent.local_only as lo

    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)

    def _boom(*a, **k):
        raise AssertionError("must not touch the network under local-only")

    monkeypatch.setattr(au, "_resolve_codex_usage_credentials", _boom)
    result = au.redeem_codex_reset_credit()
    assert result.status == "unavailable"
