"""Contract tests for the Provider Settings service + guided connect flow (§3/§4/§10)."""

from __future__ import annotations

from dataclasses import dataclass, field

from agent.provider_adapter import ConnectionStatus
from agent.provider_catalog import ProviderCatalog
from agent.provider_secret_bridge import ProviderKeyRef, ProviderSecretStore
from agent.provider_settings_service import (
    ConnectRequest,
    ConnectStep,
    ProviderSettingsService,
    ipc_get_view,
)

CAT = ProviderCatalog()
SECRET = "AIza" + "z" * 35   # valid gemini format


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

    def get(self, url, *, headers=None, timeout=5.0):
        if self.exc:
            raise self.exc
        return self.resp


@dataclass
class FakeFetch:
    secrets: dict = field(default_factory=dict)
    error: str | None = None
    error_kind: object = None

    @property
    def ok(self):
        return self.error is None


class FakeResolver:
    def __init__(self, value):
        self._value = value

    def fetch_env(self, env_var, source):
        return FakeFetch(secrets={env_var: self._value})


class RecordingWriter:
    """Fake OS secure-store writer: records the key it got, returns a NON-SECRET handle."""

    def __init__(self):
        self.saw_key = None

    def __call__(self, provider_id, key):
        self.saw_key = key
        return ProviderKeyRef(provider_id, f"{provider_id.upper()}_API_KEY", source="os")


def _svc(reg=None):
    return ProviderSettingsService(CAT, ProviderSecretStore(), reg or FakeRegistry([FakeProfile("gemini")]))


# ---- view --------------------------------------------------------------- #

def test_build_view_has_sections_and_executable_map():
    svc = _svc(FakeRegistry([FakeProfile("gemini", base_url="https://g/v1")]))
    view = svc.build_view()
    ids = {c.id for c in view.all_cards()}
    assert {"gemini", "ollama"} <= ids
    gem = next(c for c in view.all_cards() if c.id == "gemini")
    assert gem.executable is True                 # has a runtime profile


# ---- connect: cloud happy path ----------------------------------------- #

def test_connect_cloud_success_never_leaks_key():
    svc = _svc()
    writer = RecordingWriter()
    resolver = FakeResolver(SECRET)
    http = FakeHttp(resp=FakeResp(200, {"data": [{"id": "gemini-1.5"}]}))
    res = svc.connect(ConnectRequest("gemini", SECRET),
                      secret_writer=writer, resolver=resolver, http=http)
    assert res.connected and res.step is ConnectStep.CONNECTED
    assert res.models == ("gemini-1.5",)
    assert writer.saw_key == SECRET               # key reached the secure store
    assert SECRET not in repr(res)                # but NEVER appears in the renderer result


# ---- connect: invalid format never stores ------------------------------ #

def test_connect_invalid_format_does_not_store():
    svc = _svc()
    writer = RecordingWriter()
    res = svc.connect(ConnectRequest("gemini", "not-a-key"),
                      secret_writer=writer, resolver=FakeResolver(SECRET), http=FakeHttp())
    assert res.step is ConnectStep.VALIDATE_FORMAT and not res.connected
    assert writer.saw_key is None                 # nothing stored on bad format


# ---- connect: LOCAL_ONLY blocks cloud config --------------------------- #

def test_connect_local_only_blocks_cloud():
    svc = _svc()
    writer = RecordingWriter()
    res = svc.connect(ConnectRequest("gemini", SECRET), secret_writer=writer,
                      resolver=FakeResolver(SECRET), http=FakeHttp(), local_only=True)
    assert not res.connected and writer.saw_key is None


# ---- connect: local provider needs no key ------------------------------ #

def test_connect_local_provider_detects_without_key():
    svc = _svc()
    http = FakeHttp(resp=FakeResp(200, {"models": [{"name": "llama3"}]}))
    res = svc.connect(ConnectRequest("ollama"), secret_writer=RecordingWriter(),
                      resolver=FakeResolver(""), http=http)
    assert res.connected and res.models == ("llama3",)


# ---- connect: health failure surfaces status --------------------------- #

def test_connect_health_failure_reports_invalid_key():
    svc = _svc()
    http = FakeHttp(resp=FakeResp(401))
    res = svc.connect(ConnectRequest("gemini", SECRET), secret_writer=RecordingWriter(),
                      resolver=FakeResolver(SECRET), http=http)
    assert res.step is ConnectStep.HEALTH_CHECK and res.status is ConnectionStatus.INVALID_KEY


# ---- test_all: no paid calls, only health ------------------------------ #

def test_test_all_health_only():
    svc = _svc()
    svc._store.set_ref(ProviderKeyRef("gemini", "GEMINI_API_KEY", source="os"))
    http = FakeHttp(resp=FakeResp(200, {"data": []}))
    statuses = svc.test_all(resolver=FakeResolver(SECRET), http=http)
    assert statuses["gemini"] is ConnectionStatus.CONNECTED
    assert statuses["ollama"] in set(ConnectionStatus)     # local detected too


# ---- IPC handler is renderer-safe -------------------------------------- #

def test_ipc_get_view_is_renderer_safe_dict():
    svc = _svc()
    out = ipc_get_view(svc, {"local_only": False})
    assert "sections" in out and out["sections"]
    flat = repr(out)
    # no secret VALUE and no Bearer token leaks (URLs containing "api_keys" are fine)
    assert SECRET not in flat
    assert "Bearer " not in flat
    # cards expose only a boolean has_key, never a raw key field
    card = out["sections"][0]["cards"][0]
    assert isinstance(card["has_key"], bool) and "key_ref" not in card and "api_key" not in card
