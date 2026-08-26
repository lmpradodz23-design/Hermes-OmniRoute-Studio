"""REAL integration test for the provider runtime injections.

Starts an actual local HTTP server (loopback) and drives the whole probe chain through
the real UrllibHttpClient — no fakes for the transport. Proves health check + model
discovery + the guided connect flow genuinely work end-to-end. Also exercises the real
SecretSourcesResolver against a conforming fake source, and default_service assembly.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from agent.provider_adapter import ConnectionStatus
from agent.provider_catalog import ProviderCatalog
from agent.provider_probe import health_check
from agent.provider_runtime import (
    SecretSourcesResolver,
    UrllibHttpClient,
    default_service,
)
from agent.provider_secret_bridge import ProviderKeyRef, ProviderSecretStore, resolve_key
from agent.provider_settings_service import ConnectRequest, ProviderSettingsService


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):        # silence
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        auth = self.headers.get("Authorization", "")
        if self.path == "/v1/models":
            if auth == "Bearer bad":
                return self._send(401, {"error": "invalid key"})
            return self._send(200, {"data": [{"id": "m1"}, {"id": "m2"}]})
        if self.path == "/api/tags":
            return self._send(200, {"models": [{"name": "llama3"}]})
        return self._send(404, {"error": "not found"})


@pytest.fixture()
def server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    host, port = srv.server_address
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        srv.shutdown()
        srv.server_close()


HTTP = UrllibHttpClient()


# ---- real HTTP probe chain --------------------------------------------- #

def test_real_health_check_connected_with_models(server):
    r = health_check("openai-compatible", f"{server}/v1", http=HTTP, key="good")
    assert r.status is ConnectionStatus.CONNECTED
    assert r.models == ("m1", "m2")               # discovered via a REAL http round-trip


def test_real_health_check_invalid_key(server):
    r = health_check("openai-compatible", f"{server}/v1", http=HTTP, key="bad")
    assert r.status is ConnectionStatus.INVALID_KEY and r.models == ()


def test_real_ollama_tags_shape(server):
    # provider_id "ollama" routes model discovery to /api/tags (native shape)
    r = health_check("ollama", server, http=HTTP)
    assert r.status is ConnectionStatus.CONNECTED and r.models == ("llama3",)


def test_real_network_error_is_classified(server):
    # nothing is listening on this port -> transport failure -> NETWORK_ERROR
    r = health_check("openai-compatible", "http://127.0.0.1:9/v1", http=HTTP, key="x", timeout=1.0)
    assert r.status is ConnectionStatus.NETWORK_ERROR


# ---- real SecretSourcesResolver ---------------------------------------- #

@dataclass
class _FakeFetch:
    secrets: dict = field(default_factory=dict)
    error: str | None = None
    error_kind: object = None

    @property
    def ok(self):
        return self.error is None


@dataclass
class _FakeSource:
    name: str
    value: str

    def fetch(self, cfg, home_path):
        return _FakeFetch(secrets={"OPENAI_COMPATIBLE_API_KEY": self.value})


class _FakeRegistry:
    def __init__(self, sources):
        self._s = {s.name: s for s in sources}

    def get_source(self, name):
        return self._s.get(name)

    def list_sources(self):
        return list(self._s.values())


def test_real_secret_resolver_reads_mapped_var(tmp_path):
    reg = _FakeRegistry([_FakeSource("os", "sk-real-value")])
    resolver = SecretSourcesResolver(reg, home_path=tmp_path)
    out = resolve_key(ProviderKeyRef("openai-compatible", "OPENAI_COMPATIBLE_API_KEY", source="os"), resolver)
    assert out.ok and out.value_for_transport() == "sk-real-value"


def test_secret_resolver_missing_is_not_configured(tmp_path):
    reg = _FakeRegistry([])
    resolver = SecretSourcesResolver(reg, home_path=tmp_path)
    out = resolve_key(ProviderKeyRef("x", "X_KEY"), resolver)
    assert not out.ok


# ---- default_service assembly (fake registry) + end-to-end connect ------ #

@dataclass
class _Profile:
    name: str
    aliases: tuple = ()
    base_url: str = ""
    signup_url: str = ""
    supports_vision: bool = True


class _ProfReg:
    def __init__(self, profiles):
        self._p = profiles

    def get_provider_profile(self, name):
        for p in self._p:
            if p.name == name or name in p.aliases:
                return p
        return None

    def list_providers(self):
        return self._p


def test_default_service_builds_view_with_injected_registry():
    svc = default_service(registry=_ProfReg([_Profile("gemini", base_url="https://g/v1")]),
                          store=ProviderSecretStore(), catalog=ProviderCatalog())
    view = svc.build_view()
    assert any(c.id == "gemini" for c in view.all_cards())


def test_end_to_end_connect_local_provider_through_real_http(server):
    # a local provider connects with NO key, via a REAL http probe to our server's /api/tags
    cat = ProviderCatalog()
    svc = ProviderSettingsService(cat, ProviderSecretStore(), _ProfReg([]))

    # point the probe at our test server by monkeypatching local_health_url for ollama
    import agent.provider_probe as probe
    orig = probe.local_health_url
    probe.local_health_url = lambda pid: f"{server}/api/tags" if pid == "ollama" else orig(pid)
    try:
        res = svc.connect(ConnectRequest("ollama"), secret_writer=lambda *a: None,
                          resolver=None, http=HTTP)
    finally:
        probe.local_health_url = orig
    assert res.connected and res.models == ("llama3",)
