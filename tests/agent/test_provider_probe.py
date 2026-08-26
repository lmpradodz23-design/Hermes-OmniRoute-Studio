"""Contract tests for provider health-check / model-discovery / local-detection (§5/§6/§13)."""

from __future__ import annotations

from dataclasses import dataclass, field

from agent.provider_adapter import ConnectionStatus
from agent.provider_probe import (
    classify_exception,
    classify_http_status,
    detect_local,
    health_check,
    parse_models,
)


@dataclass
class FakeResp:
    status_code: int
    payload: object = None

    def json(self):
        return self.payload


@dataclass
class FakeHttp:
    resp: object = None
    exc: BaseException | None = None
    calls: list = field(default_factory=list)

    def get(self, url, *, headers=None, timeout=5.0):
        self.calls.append({"url": url, "headers": dict(headers or {}), "timeout": timeout})
        if self.exc is not None:
            raise self.exc
        return self.resp


# ---- classification ----------------------------------------------------- #

def test_classify_http_status():
    assert classify_http_status(200) is ConnectionStatus.CONNECTED
    assert classify_http_status(401) is ConnectionStatus.INVALID_KEY
    assert classify_http_status(403) is ConnectionStatus.INVALID_KEY
    assert classify_http_status(402) is ConnectionStatus.NO_QUOTA
    assert classify_http_status(429) is ConnectionStatus.RATE_LIMITED
    assert classify_http_status(503) is ConnectionStatus.PROVIDER_DOWN
    assert classify_http_status(404) is ConnectionStatus.CONFIG_ERROR


def test_classify_exception():
    assert classify_exception(TimeoutError("timed out")) is ConnectionStatus.NETWORK_ERROR
    assert classify_exception(OSError("Connection refused")) is ConnectionStatus.NETWORK_ERROR
    assert classify_exception(ValueError("weird")) is ConnectionStatus.UNKNOWN


# ---- model discovery parsing ------------------------------------------- #

def test_parse_models_openai_and_ollama_shapes():
    assert parse_models({"data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]}) == ["gpt-4o", "gpt-4o-mini"]
    assert parse_models({"models": [{"name": "llama3:8b"}, {"name": "qwen:7b"}]}, "ollama") == ["llama3:8b", "qwen:7b"]
    assert parse_models("nonsense") == []
    assert parse_models({"data": [{"nope": 1}]}) == []


# ---- health check ------------------------------------------------------- #

def test_health_check_connected_lists_models_and_sends_auth():
    http = FakeHttp(resp=FakeResp(200, {"data": [{"id": "m1"}]}))
    r = health_check("groq", "https://api.groq.com/openai/v1", http=http, key="gsk_x")
    assert r.status is ConnectionStatus.CONNECTED and r.models == ("m1",)
    assert http.calls[0]["headers"].get("Authorization") == "Bearer gsk_x"
    assert http.calls[0]["url"].endswith("/models")


def test_health_check_invalid_key_no_models():
    http = FakeHttp(resp=FakeResp(401, {"data": [{"id": "m1"}]}))
    r = health_check("groq", "https://api.groq.com/openai/v1", http=http, key="bad")
    assert r.status is ConnectionStatus.INVALID_KEY and r.models == ()


def test_health_check_exception_fails_safe_to_network_error():
    http = FakeHttp(exc=OSError("Connection refused"))
    r = health_check("groq", "https://api.groq.com/openai/v1", http=http, key="x")
    assert r.status is ConnectionStatus.NETWORK_ERROR


def test_local_health_check_sends_no_auth_and_uses_ollama_tags():
    http = FakeHttp(resp=FakeResp(200, {"models": [{"name": "llama3"}]}))
    r = health_check("ollama", "http://127.0.0.1:11434", http=http, is_local=True)
    assert r.status is ConnectionStatus.CONNECTED and r.models == ("llama3",)
    assert "Authorization" not in http.calls[0]["headers"]     # local: never sends a key
    assert http.calls[0]["url"].endswith("/api/tags")


# ---- local detection ---------------------------------------------------- #

def test_detect_local_running_vs_not_running():
    up = detect_local("ollama", http=FakeHttp(resp=FakeResp(200, {"models": [{"name": "x"}]})))
    assert up.status is ConnectionStatus.CONNECTED and up.models == ("x",)

    down = detect_local("lmstudio", http=FakeHttp(exc=OSError("Connection refused")))
    assert down.status is ConnectionStatus.PROVIDER_DOWN     # not running != hard error
