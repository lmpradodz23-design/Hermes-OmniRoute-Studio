"""Contract tests — garantem que um provider substituto encaixa sem tocar o core."""

from typing import Callable

import pytest

from whatsapp_provider.events import NormalizedEvent
from whatsapp_provider.provider import (
    ProviderStatus,
    SendResult,
    WhatsAppProvider,
    assert_conforms,
)
from whatsapp_provider.session import SessionState


class _FakeProvider(WhatsAppProvider):
    """Provider mínimo conforme — prova que o contrato é implementável sem OpenWA."""

    name = "fake"

    def capabilities(self):
        return frozenset({"send_text"})

    def start(self): ...
    def stop(self): ...

    def get_status(self):
        return ProviderStatus("fake", "s1", SessionState.CONNECTED, healthy=True)

    def health_check(self):
        return True

    def send_text(self, chat_id, text):
        return SendResult(ok=True, message_id="FAKE_ID")

    def subscribe_events(self, handler: Callable[[NormalizedEvent], None]):
        ...


def test_conforming_provider_has_no_missing_methods():
    assert assert_conforms(_FakeProvider) == []


def test_incomplete_provider_is_detected():
    class Broken(WhatsAppProvider):
        name = "broken"
        # não implementa nada
    missing = assert_conforms(Broken)
    # todas as abstratas ainda são abstratas → faltando
    assert "send_text" in missing
    assert "start" in missing


def test_abstract_provider_cannot_be_instantiated():
    with pytest.raises(TypeError):
        WhatsAppProvider()  # type: ignore


def test_send_result_success_carries_id_failure_carries_error():
    ok = SendResult(ok=True, message_id="X")
    fail = SendResult(ok=False, error="logged out")
    assert ok.message_id == "X" and ok.error == ""
    assert fail.ok is False and fail.error == "logged out"


def test_fake_provider_roundtrip():
    p = _FakeProvider()
    p.start()
    assert p.health_check() is True
    assert p.get_status().state == SessionState.CONNECTED
    assert p.send_text("5511@c.us", "oi").message_id == "FAKE_ID"
    assert "send_text" in p.capabilities()
