"""Superfície MCP — allowlist, gate de capacidade, schema, e SEM sucesso falso."""

import pytest

from whatsapp_provider.capabilities import WhatsAppCapability, WhatsAppGrants
from whatsapp_provider.mcp_tools import (
    TOOL_ALLOWLIST,
    ToolOutcome,
    WhatsAppMcpDispatcher,
)
from whatsapp_provider.provider import ProviderStatus, SendResult, WhatsAppProvider
from whatsapp_provider.session import SessionState


class _StubProvider(WhatsAppProvider):
    name = "stub"

    def __init__(self, state=SessionState.CONNECTED, caps=frozenset()):
        self._state = state
        self._caps = caps
        self.sent = []

    def capabilities(self):
        return self._caps

    def start(self):
        self._state = SessionState.QR_REQUIRED

    def stop(self):
        self._state = SessionState.DISCONNECTED

    def get_status(self):
        return ProviderStatus("openwa", "s1", self._state, healthy=self._state == SessionState.CONNECTED)

    def health_check(self):
        return self._state == SessionState.CONNECTED

    def send_text(self, chat_id, text):
        self.sent.append((chat_id, text))
        return SendResult(ok=True, message_id="REAL_ID")

    def subscribe_events(self, handler):
        ...


def _grants_all():
    return WhatsAppGrants(granted=frozenset(WhatsAppCapability))


def test_tool_outside_allowlist_is_denied():
    d = WhatsAppMcpDispatcher(_StubProvider())
    r = d.call("whatsapp.exec_shell", {}, _grants_all())
    assert r.outcome == ToolOutcome.DENIED


def test_raw_openwa_api_is_not_exposed():
    # A allowlist é pequena e explícita — não a API OpenWA inteira.
    assert set(TOOL_ALLOWLIST) == {
        "whatsapp.status", "whatsapp.sessions", "whatsapp.health",
        "whatsapp.get_chats", "whatsapp.get_messages",
        "whatsapp.connect", "whatsapp.disconnect",
        "whatsapp.send_text", "whatsapp.send_media",
    }


def test_send_requires_send_capability():
    d = WhatsAppMcpDispatcher(_StubProvider())
    only_read = WhatsAppGrants()  # default = só READ
    r = d.call("whatsapp.send_text", {"recipient": "5511999@c.us", "text": "oi"}, only_read)
    assert r.outcome == ToolOutcome.DENIED


def test_send_to_unauthenticated_session_is_not_false_success():
    # A regra §4: enquanto a sessão não autenticar, send NÃO retorna SUCCESS.
    d = WhatsAppMcpDispatcher(_StubProvider(state=SessionState.QR_REQUIRED))
    r = d.call("whatsapp.send_text", {"recipient": "5511999@c.us", "text": "oi"},
               WhatsAppGrants().with_granted(WhatsAppCapability.SEND))
    assert r.outcome == ToolOutcome.QR_REQUIRED


def test_send_to_logged_out_session_reports_not_authenticated():
    d = WhatsAppMcpDispatcher(_StubProvider(state=SessionState.LOGGED_OUT))
    r = d.call("whatsapp.send_text", {"recipient": "5511999@c.us", "text": "oi"},
               WhatsAppGrants().with_granted(WhatsAppCapability.SEND))
    assert r.outcome == ToolOutcome.NOT_AUTHENTICATED


def test_send_on_connected_session_returns_real_id():
    stub = _StubProvider(state=SessionState.CONNECTED)
    d = WhatsAppMcpDispatcher(stub)
    r = d.call("whatsapp.send_text", {"recipient": "5511999@c.us", "text": "oi"},
               WhatsAppGrants().with_granted(WhatsAppCapability.SEND))
    assert r.outcome == ToolOutcome.OK
    assert r.data["message_id"] == "REAL_ID"
    assert stub.sent == [("5511999@c.us", "oi")]


@pytest.mark.parametrize("bad", [
    {"recipient": "5511@c.us; rm -rf /", "text": "x"},
    {"recipient": "../../etc@c.us", "text": "x"},
    {"recipient": "5511999@c.us", "text": ""},
    {"recipient": "", "text": "x"},
])
def test_send_schema_validation_rejects_bad_input(bad):
    d = WhatsAppMcpDispatcher(_StubProvider())
    r = d.call("whatsapp.send_text", bad, WhatsAppGrants().with_granted(WhatsAppCapability.SEND))
    assert r.outcome == ToolOutcome.INVALID


def test_send_media_path_traversal_rejected(tmp_path):
    d = WhatsAppMcpDispatcher(_StubProvider(caps=frozenset({"send_media"})), media_root=str(tmp_path))
    r = d.call("whatsapp.send_media",
               {"recipient": "5511999@c.us", "path": "../../etc/passwd"},
               WhatsAppGrants().with_granted(WhatsAppCapability.SEND_MEDIA))
    assert r.outcome == ToolOutcome.INVALID


def test_status_is_read_only_and_works_offline():
    d = WhatsAppMcpDispatcher(_StubProvider(state=SessionState.DISCONNECTED))
    r = d.call("whatsapp.status", {}, WhatsAppGrants())
    assert r.outcome == ToolOutcome.OK
    assert r.data["state"] == "disconnected"
