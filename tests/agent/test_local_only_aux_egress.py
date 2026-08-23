"""LOCAL_ONLY — auxiliary egress boundary (compression/title/vision/MoA/fallback).

Proves the second egress chokepoint (auxiliary_client) is fail-closed under
local-only, matching the main route. Two layers:

  1. PURE policy matrix (egress_denial_reason) — always runs (stdlib only).
  2. WIRED chokepoint (_create_openai_client) — skips only if auxiliary_client's
     heavy deps are unavailable in the test env; when it runs it proves the real
     wiring, not just the helper.

Canary: deleting the `_enforce_local_only_egress(base_url)` call in
_create_openai_client must make `test_wired_cloud_blocked` fail.
"""

import importlib

import pytest

from agent.local_only import (
    LocalOnlyConfig,
    LocalOnlyPolicy,
    LocalOnlyViolation,
    egress_denial_reason,
)


def test_authorize_tool_blocks_cloud_gen_tools_under_local_only():
    pol = LocalOnlyPolicy(LocalOnlyConfig(enabled=True))
    assert pol.authorize_tool("image_generate", {}).allowed is False
    assert pol.authorize_tool("video_generate", {}).allowed is False


def test_authorize_tool_allows_gen_tools_when_local_only_off():
    pol = LocalOnlyPolicy(LocalOnlyConfig(enabled=False))
    assert pol.authorize_tool("image_generate", {}).allowed is True


def test_authorize_tool_still_allows_a_local_tool_under_local_only():
    pol = LocalOnlyPolicy(LocalOnlyConfig(enabled=True))
    assert pol.authorize_tool("read_file", {}).allowed is True


def test_subagent_inherits_local_only_from_shared_config():
    # local_only is a persisted config key (security.local_only). Child agents are
    # built through AIAgent()->agent_init from the SAME _load_config() source
    # (delegate_tool._build_child_agent overrides only credentials/model/transport,
    # never security). So parent and child derive the same policy.
    security = {"local_only": True}
    parent = LocalOnlyPolicy(LocalOnlyConfig.from_mapping(security))
    child = LocalOnlyPolicy(LocalOnlyConfig.from_mapping(security))
    assert parent.config.enabled is True
    assert child.config.enabled is True
    # Even a child explicitly handed a CLOUD base_url (delegation override) is
    # denied on its own main route by the inherited policy — override can't escape.
    assert child.authorize_route(provider="anthropic", base_url="https://api.anthropic.com").allowed is False
    # A child pointed at a loopback endpoint is allowed.
    assert child.authorize_route(provider="ollama", base_url="http://localhost:11434").allowed is True


def test_local_only_off_config_does_not_gate():
    # Regression: a config without local_only (or false) yields a disabled policy.
    for security in ({}, {"local_only": False}, {"local_only": "no"}):
        pol = LocalOnlyPolicy(LocalOnlyConfig.from_mapping(security))
        assert pol.config.enabled is False
        assert pol.authorize_route(provider="anthropic", base_url="https://api.anthropic.com").allowed is True

CLOUD_ROUTES = [
    ("openai", "https://api.openai.com/v1"),
    ("anthropic", "https://api.anthropic.com"),
    ("gemini", "https://generativelanguage.googleapis.com"),
    ("openrouter", "https://openrouter.ai/api/v1"),
    ("azure", "https://myresource.openai.azure.com"),
    ("", ""),  # empty base_url → OpenAI SDK defaults to api.openai.com → must DENY
    ("some-cloud", "https://example.com/v1"),
]

LOCAL_ROUTES = [
    ("ollama", "http://localhost:11434/v1"),
    ("lmstudio", "http://127.0.0.1:1234/v1"),
    ("", "http://host.docker.internal:11434"),
    ("ollama", ""),  # local provider + empty base_url → allowed by policy
]


@pytest.mark.parametrize("provider,base_url", CLOUD_ROUTES)
def test_cloud_route_denied(provider, base_url):
    assert egress_denial_reason(provider=provider, base_url=base_url) != ""


@pytest.mark.parametrize("provider,base_url", LOCAL_ROUTES)
def test_local_route_allowed(provider, base_url):
    assert egress_denial_reason(provider=provider, base_url=base_url) == ""


# ── Wired chokepoint (real auxiliary_client) ────────────────────────────────
try:
    aux = importlib.import_module("agent.auxiliary_client")
except Exception:  # heavy deps not present in this env
    aux = None

needs_aux = pytest.mark.skipif(aux is None, reason="auxiliary_client deps unavailable in this env")


@needs_aux
def test_wired_cloud_blocked():
    token = aux.set_runtime_main("openai", "gpt-4o", base_url="https://api.openai.com/v1", local_only=True)
    try:
        with pytest.raises(LocalOnlyViolation):
            aux._create_openai_client(api_key="k", base_url="https://api.openai.com/v1")
    finally:
        aux.reset_runtime_main(token)


@needs_aux
def test_wired_empty_base_url_blocked_defaults_to_cloud():
    token = aux.set_runtime_main("openai", "gpt-4o", base_url="", local_only=True)
    try:
        with pytest.raises(LocalOnlyViolation):
            aux._create_openai_client(api_key="k", base_url="")
    finally:
        aux.reset_runtime_main(token)


@needs_aux
def test_wired_loopback_allowed_under_local_only():
    token = aux.set_runtime_main("ollama", "llama3", base_url="http://localhost:11434/v1", local_only=True)
    try:
        client = aux._create_openai_client(api_key="k", base_url="http://localhost:11434/v1")
        assert client is not None
    finally:
        aux.reset_runtime_main(token)


@needs_aux
def test_wired_local_only_off_allows_cloud():
    token = aux.set_runtime_main("openai", "gpt-4o", base_url="https://api.openai.com/v1", local_only=False)
    try:
        client = aux._create_openai_client(api_key="k", base_url="https://api.openai.com/v1")
        assert client is not None
    finally:
        aux.reset_runtime_main(token)


@needs_aux
def test_wired_no_context_no_enforcement(monkeypatch):
    # No runtime context AND persisted config not local-only → cloud allowed (no regression).
    monkeypatch.setattr(aux, "_config_local_only_fallback", lambda: False)
    client = aux._create_openai_client(api_key="k", base_url="https://api.openai.com/v1")
    assert client is not None


@needs_aux
def test_background_no_context_gated_by_persisted_config(monkeypatch):
    # §8 residual closed: a background/CLI aux call (no turn context) still honors
    # the PERSISTED security.local_only via the config fallback.
    monkeypatch.setattr(aux, "_config_local_only_fallback", lambda: True)
    with pytest.raises(LocalOnlyViolation):
        aux._create_openai_client(api_key="k", base_url="https://api.openai.com/v1")


@needs_aux
def test_background_no_context_allows_loopback_when_config_on(monkeypatch):
    monkeypatch.setattr(aux, "_config_local_only_fallback", lambda: True)
    client = aux._create_openai_client(api_key="k", base_url="http://localhost:11434/v1")
    assert client is not None


@needs_aux
def test_active_turn_context_overrides_config_fallback(monkeypatch):
    # A turn that is explicitly local_only=False is authoritative — the config
    # fallback must NOT override it (context wins when present).
    monkeypatch.setattr(aux, "_config_local_only_fallback", lambda: True)
    token = aux.set_runtime_main("openai", "gpt", base_url="https://api.openai.com/v1", local_only=False)
    try:
        client = aux._create_openai_client(api_key="k", base_url="https://api.openai.com/v1")
        assert client is not None
    finally:
        aux.reset_runtime_main(token)


@needs_aux
def test_wired_native_async_adapter_blocked_via_to_async_client():
    # Adversarial review P0: native adapters (Anthropic/Bedrock/Gemini-native/Codex)
    # build their own clients and the async gate used to sit AFTER the isinstance
    # early-returns. Subclass a REAL native type so the object hits the
    # AnthropicAuxiliaryClient isinstance early-return — only the TOP gate can
    # catch it (the generic-tail gate is never reached for this object).
    class _FakeNative(aux.AnthropicAuxiliaryClient):
        def __init__(self):  # bypass the real __init__
            self.api_key = "k"
            self.base_url = "https://api.anthropic.com"

    token = aux.set_runtime_main("anthropic", "claude", base_url="https://api.anthropic.com", local_only=True)
    try:
        with pytest.raises(LocalOnlyViolation):
            aux._to_async_client(_FakeNative(), "claude")
    finally:
        aux.reset_runtime_main(token)


@needs_aux
def test_wired_native_async_adapter_loopback_allowed():
    class _FakeLocal:
        api_key = "k"
        base_url = "http://localhost:11434/v1"

    token = aux.set_runtime_main("ollama", "llama3", base_url="http://localhost:11434/v1", local_only=True)
    try:
        client, model = aux._to_async_client(_FakeLocal(), "llama3")
        assert model == "llama3"
    finally:
        aux.reset_runtime_main(token)


@needs_aux
def test_resolve_provider_client_wrapper_blocks_native_cloud(monkeypatch):
    # Adversarial review P0 (sync path): resolve_provider_client is the single sync
    # producer; the wrapper enforces on the resolved client's base_url regardless
    # of which native adapter built it.
    class _FakeAnthropic:
        base_url = "https://api.anthropic.com"

    monkeypatch.setattr(aux, "_resolve_provider_client_impl", lambda *a, **k: (_FakeAnthropic(), "claude"))
    token = aux.set_runtime_main("anthropic", "claude", base_url="https://api.anthropic.com", local_only=True)
    try:
        with pytest.raises(LocalOnlyViolation):
            aux.resolve_provider_client("anthropic", "claude")
    finally:
        aux.reset_runtime_main(token)


@needs_aux
def test_resolve_provider_client_wrapper_allows_loopback(monkeypatch):
    class _FakeLocal:
        base_url = "http://127.0.0.1:1234/v1"

    monkeypatch.setattr(aux, "_resolve_provider_client_impl", lambda *a, **k: (_FakeLocal(), "m"))
    token = aux.set_runtime_main("lmstudio", "m", base_url="http://127.0.0.1:1234/v1", local_only=True)
    try:
        client, model = aux.resolve_provider_client("lmstudio", "m")
        assert model == "m"
    finally:
        aux.reset_runtime_main(token)


@needs_aux
def test_fallback_chain_skips_cloud_and_lets_loopback_win(monkeypatch):
    # Architecture review P2: under local-only, a raising cloud provider in the
    # fallback chain must be SKIPPED (not abort the chain), so a later loopback
    # provider still wins. Without the try/except around try_fn() this raises out.
    class _Local:
        base_url = "http://localhost:11434/v1"

    def cloud_fn():
        raise LocalOnlyViolation("blocked cloud in chain")

    def local_fn():
        return _Local(), "llama3"

    monkeypatch.setattr(aux, "_get_provider_chain", lambda: [("openrouter", cloud_fn), ("local/custom", local_fn)])
    monkeypatch.setattr(aux, "_is_provider_unhealthy", lambda label: False)

    token = aux.set_runtime_main("ollama", "llama3", base_url="http://localhost:11434/v1", local_only=True)
    try:
        client, model, label = aux._try_payment_fallback("openai", task="compression")
        assert label == "local/custom"
        assert model == "llama3"
    finally:
        aux.reset_runtime_main(token)


@needs_aux
def test_fallback_belt_and_suspenders_denies_nonraising_cloud_client(monkeypatch):
    # QA review: a builder that returns a cloud client WITHOUT raising (the shape
    # of a native adapter, e.g. GeminiNativeClient, whose per-site gate was
    # bypassed) must still be denied by the post-check, so a later loopback wins.
    class _Cloud:
        base_url = "https://generativelanguage.googleapis.com"

    class _Local:
        base_url = "http://localhost:11434/v1"

    monkeypatch.setattr(
        aux,
        "_get_provider_chain",
        lambda: [("gemini", lambda: (_Cloud(), "g")), ("local/custom", lambda: (_Local(), "llama3"))],
    )
    monkeypatch.setattr(aux, "_is_provider_unhealthy", lambda label: False)

    token = aux.set_runtime_main("ollama", "llama3", base_url="http://localhost:11434/v1", local_only=True)
    try:
        client, model, label = aux._try_payment_fallback("openai", task="compression")
        assert label == "local/custom"
        assert model == "llama3"
    finally:
        aux.reset_runtime_main(token)


@needs_aux
def test_wired_enforcement_survives_copy_context_thread():
    # CRITICAL: auxiliary provider calls run in a worker thread via
    # contextvars.copy_context().run() (auxiliary_client._run_protected_sync_provider_call).
    # Prove the local_only flag propagates across that boundary — otherwise the
    # gate would silently not fire for compression/title/vision.
    import contextvars
    import threading

    token = aux.set_runtime_main("openai", "gpt-4o", base_url="https://api.openai.com/v1", local_only=True)
    try:
        ctx = contextvars.copy_context()
        result = {}

        def worker():
            try:
                aux._create_openai_client(api_key="k", base_url="https://api.openai.com/v1")
                result["raised"] = False
            except LocalOnlyViolation:
                result["raised"] = True
            except Exception as exc:  # pragma: no cover - would indicate a different failure
                result["raised"] = False
                result["other"] = repr(exc)

        t = threading.Thread(target=ctx.run, args=(worker,))
        t.start()
        t.join(timeout=10)
        assert result.get("raised") is True, f"gate did not fire in worker thread: {result}"
    finally:
        aux.reset_runtime_main(token)
