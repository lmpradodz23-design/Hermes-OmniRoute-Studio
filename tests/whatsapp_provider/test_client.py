"""Testes do EasyApiClient — auth local Hermes↔OpenWA, sem rede.

Prova: a apiKey vai só no header (nunca URL/body/log/repr); o path vem só da
allowlist; a URL é sempre o base_url loopback; e o transporte injetado é o único
ponto de rede (aqui, um fake).
"""

import pytest

from whatsapp_provider.client import (
    API_KEY_HEADER,
    ENDPOINT_ALLOWLIST,
    EasyApiClient,
    EasyApiClientError,
    EasyApiRequest,
    EasyApiResponse,
)
from whatsapp_provider.easyapi import EasyApiConfig


KEY = "k" * 40


def _config():
    return EasyApiConfig(api_key=KEY, host="127.0.0.1", port=8080, session_id="hermes")


class CaptureTransport:
    def __init__(self, response=None):
        self.requests = []
        self.response = response or EasyApiResponse(status=200, body={"state": "CONNECTED"})

    def __call__(self, req):
        self.requests.append(req)
        return self.response


def test_api_key_goes_in_header_only_not_url():
    t = CaptureTransport()
    c = EasyApiClient(_config(), t)
    c.get_connection_state()
    req = t.requests[0]
    assert req.headers[API_KEY_HEADER] == KEY
    assert KEY not in req.url
    assert "127.0.0.1:8080" in req.url


def test_send_text_key_never_in_url_or_body():
    t = CaptureTransport(EasyApiResponse(status=200, body={"id": "true_abc"}))
    c = EasyApiClient(_config(), t)
    c.send_text("5511999999999@c.us", "olá")
    req = t.requests[0]
    assert KEY not in req.url
    assert KEY not in str(req.json)
    assert req.json == {"args": {"to": "5511999999999@c.us", "content": "olá"}}


def test_redacted_masks_the_key():
    c = EasyApiClient(_config(), CaptureTransport())
    req = c.build("sendText", args={"to": "1@c.us", "content": "x"})
    red = req.redacted()
    assert red["headers"][API_KEY_HEADER] == "[REDACTED]"
    assert KEY not in str(red)


def test_repr_never_leaks_key():
    c = EasyApiClient(_config(), CaptureTransport())
    req = c.build("getConnectionState", method="GET")
    assert KEY not in repr(req)
    assert KEY not in repr(c)
    assert "redacted" in repr(req)


def test_endpoint_outside_allowlist_is_rejected():
    c = EasyApiClient(_config(), CaptureTransport())
    with pytest.raises(EasyApiClientError):
        c.build("evalRawApi")
    with pytest.raises(EasyApiClientError):
        c.build("../../etc/passwd")


def test_url_is_always_loopback_base():
    c = EasyApiClient(_config(), CaptureTransport())
    for ep in ENDPOINT_ALLOWLIST:
        req = c.build(ep, method="GET")
        assert req.url.startswith("http://127.0.0.1:8080/")


def test_send_text_validates_chat_id():
    from whatsapp_provider.validation import WhatsAppValidationError
    c = EasyApiClient(_config(), CaptureTransport())
    with pytest.raises(WhatsAppValidationError):
        c.send_text("not-a-valid-id", "hi")


def test_transport_is_the_only_network_point():
    """Sem transporte real, nenhuma rede acontece — o fake captura tudo."""
    t = CaptureTransport(EasyApiResponse(status=200, body={"ok": True}))
    c = EasyApiClient(_config(), t)
    resp = c.get_connection_state()
    assert resp.ok is True
    assert len(t.requests) == 1


def test_response_ok_property():
    assert EasyApiResponse(status=200).ok is True
    assert EasyApiResponse(status=204).ok is True
    assert EasyApiResponse(status=401).ok is False
    assert EasyApiResponse(status=500).ok is False
