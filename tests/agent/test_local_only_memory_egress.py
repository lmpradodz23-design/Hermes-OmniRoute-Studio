"""LOCAL_ONLY — memory-plugin egress (mem0). Under local-only, mem0 must not
send user memories/turns to a remote service: Platform (cloud) and any remote
self-hosted/OSS route are denied BEFORE a backend (and thus any network) exists.
Local loopback OSS/self-hosted is allowed. Reuses the same loopback policy as
model egress. hindsight embeds locally (sentence_transformers) → not covered here.
"""

import importlib

import pytest

mem0 = None
try:
    mem0 = importlib.import_module("plugins.memory.mem0")
except Exception:
    mem0 = None

needs_mem0 = pytest.mark.skipif(mem0 is None, reason="mem0 plugin import unavailable")


def _make(mode, host, config):
    obj = object.__new__(mem0.Mem0MemoryProvider)
    obj._mode = mode
    obj._host = host
    obj._config = config
    return obj


@needs_mem0
def test_platform_cloud_denied_under_local_only(monkeypatch):
    monkeypatch.setattr(mem0, "config_local_only_enabled", lambda: True, raising=False)
    import agent.local_only as lo
    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    p = _make("platform", "", {})
    assert p._local_only_denial() != ""  # cloud denied
    assert p._create_backend() is None


@needs_mem0
def test_selfhosted_remote_denied_and_loopback_allowed(monkeypatch):
    import agent.local_only as lo
    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    remote = _make("selfhosted", "https://mem0.example.com", {})
    assert remote._local_only_denial() != ""
    local = _make("selfhosted", "http://127.0.0.1:8888", {})
    assert local._local_only_denial() == ""


@needs_mem0
def test_oss_remote_embedder_denied(monkeypatch):
    import agent.local_only as lo
    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    # openai embedder with no base_url → defaults to cloud → denied
    cfg = {"oss": {"embedder": {"provider": "openai", "config": {}},
                   "llm": {"provider": "ollama", "config": {"ollama_base_url": "http://localhost:11434"}},
                   "vector_store": {"provider": "qdrant", "config": {"url": "http://localhost:6333"}}}}
    p = _make("oss", "", cfg)
    assert p._local_only_denial() != ""


@needs_mem0
def test_oss_api_base_remote_under_local_provider_denied(monkeypatch):
    # P0 (adversarial): provider name is "ollama" (local) but api_base points
    # remote; _backend.py remaps api_base onto the canonical base-url key, so this
    # would egress. The broadened extraction must deny it.
    import agent.local_only as lo
    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    cfg = {"oss": {"embedder": {"provider": "ollama", "config": {"model": "x", "api_base": "https://evil.example.com/v1"}},
                   "llm": {"provider": "ollama", "config": {"ollama_base_url": "http://localhost:11434"}},
                   "vector_store": {"provider": "qdrant", "config": {"url": "http://localhost:6333"}}}}
    p = _make("oss", "", cfg)
    assert p._local_only_denial() != ""


@needs_mem0
def test_oss_all_local_allowed(monkeypatch):
    import agent.local_only as lo
    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    cfg = {"oss": {"embedder": {"provider": "ollama", "config": {"ollama_base_url": "http://localhost:11434"}},
                   "llm": {"provider": "ollama", "config": {"ollama_base_url": "http://127.0.0.1:11434"}},
                   "vector_store": {"provider": "qdrant", "config": {"url": "http://localhost:6333"}}}}
    p = _make("oss", "", cfg)
    assert p._local_only_denial() == ""


@needs_mem0
def test_local_only_off_allows_cloud(monkeypatch):
    import agent.local_only as lo
    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: False)
    p = _make("platform", "", {})
    assert p._local_only_denial() == ""


@needs_mem0
def test_canary_oss_remote_vector_store_denied(monkeypatch):
    # CANARY intent: a remote vector store (memories leave the machine) is denied.
    import agent.local_only as lo
    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    cfg = {"oss": {"embedder": {"provider": "ollama", "config": {"ollama_base_url": "http://localhost:11434"}},
                   "llm": {"provider": "ollama", "config": {"ollama_base_url": "http://localhost:11434"}},
                   "vector_store": {"provider": "qdrant", "config": {"url": "https://xyz.cloud.qdrant.io"}}}}
    p = _make("oss", "", cfg)
    assert p._local_only_denial() != ""


# ── ACTIVATION-path gate (public local_only_denial, pre-initialize) ─────────
# The activation gate (agent_init) calls the PUBLIC local_only_denial() on a
# provider that has NOT been initialize()d — so it must resolve config from disk
# via _load_config(), not from the platform/None __init__ defaults (which would
# blindly deny even a valid local OSS config: the F1 regression).


@needs_mem0
def test_activation_gate_reads_config_local_oss_allowed(monkeypatch):
    import agent.local_only as lo
    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    monkeypatch.setattr(mem0, "config_local_only_enabled", lambda: True, raising=False)
    cfg = {"mode": "oss", "host": "", "oss": {
        "embedder": {"provider": "ollama", "config": {"ollama_base_url": "http://127.0.0.1:11434"}},
        "llm": {"provider": "ollama", "config": {"ollama_base_url": "http://127.0.0.1:11434"}},
        "vector_store": {"provider": "qdrant", "config": {"url": "http://127.0.0.1:6333"}}}}
    monkeypatch.setattr(mem0, "_load_config", lambda: cfg)
    # Fresh, uninitialized instance — exactly what the activation gate sees.
    p = object.__new__(mem0.Mem0MemoryProvider)
    assert p.local_only_denial() == "", "a fully-local OSS config must NOT be blindly denied at activation"


@needs_mem0
def test_activation_gate_reads_config_platform_denied(monkeypatch):
    import agent.local_only as lo
    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    monkeypatch.setattr(mem0, "_load_config", lambda: {"mode": "platform", "host": ""})
    p = object.__new__(mem0.Mem0MemoryProvider)
    assert p.local_only_denial() != ""


@needs_mem0
def test_activation_gate_reads_config_oss_remote_embedder_denied(monkeypatch):
    import agent.local_only as lo
    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    cfg = {"mode": "oss", "host": "", "oss": {
        "embedder": {"provider": "openai", "config": {}},
        "llm": {"provider": "ollama", "config": {"ollama_base_url": "http://localhost:11434"}},
        "vector_store": {"provider": "qdrant", "config": {"url": "http://localhost:6333"}}}}
    monkeypatch.setattr(mem0, "_load_config", lambda: cfg)
    p = object.__new__(mem0.Mem0MemoryProvider)
    assert p.local_only_denial() != ""


@needs_mem0
def test_oss_bare_remote_host_qdrant_denied(monkeypatch):
    # mem0 qdrant vector_store uses {host, port} with NO scheme. A remote host
    # here still egresses memories → must be denied (scheme-less extraction).
    import agent.local_only as lo
    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    cfg = {"oss": {"embedder": {"provider": "ollama", "config": {"ollama_base_url": "http://127.0.0.1:11434"}},
                   "llm": {"provider": "ollama", "config": {"ollama_base_url": "http://127.0.0.1:11434"}},
                   "vector_store": {"provider": "qdrant", "config": {"host": "xyz.cloud.qdrant.io", "port": 6333}}}}
    p = _make("oss", "", cfg)
    assert p._local_only_denial() != ""


@needs_mem0
def test_oss_bare_local_host_qdrant_allowed(monkeypatch):
    # A bare loopback host must NOT be over-denied.
    import agent.local_only as lo
    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    cfg = {"oss": {"embedder": {"provider": "ollama", "config": {"ollama_base_url": "http://127.0.0.1:11434"}},
                   "llm": {"provider": "ollama", "config": {"ollama_base_url": "http://127.0.0.1:11434"}},
                   "vector_store": {"provider": "qdrant", "config": {"host": "localhost", "port": 6333}}}}
    p = _make("oss", "", cfg)
    assert p._local_only_denial() == ""


@needs_mem0
def test_oss_default_on_disk_qdrant_allowed(monkeypatch):
    # N2 (adversarial): the DEFAULT mem0 vector store is an embedded on-disk
    # qdrant ({path: ~/.hermes/mem0_qdrant}) — fully local, zero network. It must
    # ACTIVATE, not be over-denied by the provider-name fallback.
    import agent.local_only as lo
    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    cfg = {"oss": {"embedder": {"provider": "ollama", "config": {"ollama_base_url": "http://127.0.0.1:11434"}},
                   "llm": {"provider": "ollama", "config": {"ollama_base_url": "http://127.0.0.1:11434"}},
                   "vector_store": {"provider": "qdrant", "config": {"path": "~/.hermes/mem0_qdrant"}}}}
    p = _make("oss", "", cfg)
    assert p._local_only_denial() == ""


@needs_mem0
def test_oss_on_disk_path_does_not_launder_remote_route(monkeypatch):
    # A path key must NOT rescue a block that ALSO carries an explicit remote
    # route (a remote server never becomes local via a path key).
    import agent.local_only as lo
    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    cfg = {"oss": {"embedder": {"provider": "ollama", "config": {"ollama_base_url": "http://127.0.0.1:11434"}},
                   "llm": {"provider": "ollama", "config": {"ollama_base_url": "http://127.0.0.1:11434"}},
                   "vector_store": {"provider": "qdrant",
                                    "config": {"path": "~/.hermes/q", "url": "https://xyz.cloud.qdrant.io"}}}}
    p = _make("oss", "", cfg)
    assert p._local_only_denial() != ""


@needs_mem0
def test_oss_path_value_that_is_a_url_denied(monkeypatch):
    # N2b: a "path" key whose VALUE is a URL is a remote locator, not a
    # filesystem path — it must be routed and denied, not trusted as local.
    import agent.local_only as lo
    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    cfg = {"oss": {"embedder": {"provider": "ollama", "config": {"ollama_base_url": "http://127.0.0.1:11434"}},
                   "llm": {"provider": "ollama", "config": {"ollama_base_url": "http://127.0.0.1:11434"}},
                   "vector_store": {"provider": "qdrant", "config": {"path": "https://evil.example.com/db"}}}}
    p = _make("oss", "", cfg)
    assert p._local_only_denial() != ""


@needs_mem0
def test_oss_remote_graph_store_denied(monkeypatch):
    # Defense-in-depth: a remote graph_store (memories/entities leave the machine)
    # is denied even though OSSBackend does not wire it today.
    import agent.local_only as lo
    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    cfg = {"oss": {"embedder": {"provider": "ollama", "config": {"ollama_base_url": "http://127.0.0.1:11434"}},
                   "llm": {"provider": "ollama", "config": {"ollama_base_url": "http://127.0.0.1:11434"}},
                   "vector_store": {"provider": "qdrant", "config": {"path": "~/.hermes/q"}},
                   "graph_store": {"provider": "neo4j", "config": {"url": "https://graph.example.com"}}}}
    p = _make("oss", "", cfg)
    assert p._local_only_denial() != ""


@needs_mem0
def test_oss_remote_reranker_denied(monkeypatch):
    import agent.local_only as lo
    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    cfg = {"oss": {"embedder": {"provider": "ollama", "config": {"ollama_base_url": "http://127.0.0.1:11434"}},
                   "llm": {"provider": "ollama", "config": {"ollama_base_url": "http://127.0.0.1:11434"}},
                   "vector_store": {"provider": "qdrant", "config": {"path": "~/.hermes/q"}},
                   "reranker": {"provider": "cohere", "config": {"api_base": "https://api.cohere.ai"}}}}
    p = _make("oss", "", cfg)
    assert p._local_only_denial() != ""


@needs_mem0
def test_oss_empty_embedder_block_denied(monkeypatch):
    # REGRESSION (P1): a present-but-empty embedder {} defaults to the OpenAI
    # CLOUD in mem0, so it must be DENIED — the optional-block skip must NOT
    # apply to embedder/llm/vector_store.
    import agent.local_only as lo
    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    cfg = {"oss": {"embedder": {},
                   "llm": {"provider": "ollama", "config": {"ollama_base_url": "http://127.0.0.1:11434"}},
                   "vector_store": {"provider": "qdrant", "config": {"path": "~/.hermes/q"}}}}
    p = _make("oss", "", cfg)
    assert p._local_only_denial() != "", "empty embedder (cloud default) must be denied"


@needs_mem0
def test_oss_empty_llm_block_denied(monkeypatch):
    import agent.local_only as lo
    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    cfg = {"oss": {"embedder": {"provider": "ollama", "config": {"ollama_base_url": "http://127.0.0.1:11434"}},
                   "llm": {},
                   "vector_store": {"provider": "qdrant", "config": {"path": "~/.hermes/q"}}}}
    p = _make("oss", "", cfg)
    assert p._local_only_denial() != "", "empty llm (cloud default) must be denied"


@needs_mem0
def test_canary_mem0_denial_is_load_bearing(monkeypatch):
    # CANARY: this asserts the mem0 gate actively DENIES a remote platform config.
    # If _local_only_denial were gutted to always return "" (gate removed), this
    # fails — locking the gate in place.
    import agent.local_only as lo
    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    p = _make("platform", "", {})
    assert p._local_only_denial() != "", "mem0 platform egress MUST be denied under local-only"


@needs_mem0
def test_oss_remote_endpoint_under_unusual_key_denied(monkeypatch):
    # N3 (defense-in-depth): a remote endpoint hidden under a non-standard key
    # (server/node/address) must not ride the local provider-name allowlist.
    import agent.local_only as lo
    monkeypatch.setattr(lo, "config_local_only_enabled", lambda: True)
    cfg = {"oss": {"embedder": {"provider": "ollama", "config": {"server": "evil.example.com"}},
                   "llm": {"provider": "ollama", "config": {"ollama_base_url": "http://127.0.0.1:11434"}},
                   "vector_store": {"provider": "qdrant", "config": {"path": "~/.hermes/q"}}}}
    p = _make("oss", "", cfg)
    assert p._local_only_denial() != ""
