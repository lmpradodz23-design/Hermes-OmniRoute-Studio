"""Testes do MemorySanitizer — a fronteira única da memória do WhatsApp.

Prova a regra dura: nada chega à memória com segredo, token, apiKey, cookie, QR
(dataURL) ou bytes de mídia; texto é redigido e limitado; metadata sensível é
descartada; e a verificação final falha fechado se algo escapar.
"""

import pytest

from whatsapp_provider.events import EventType, NormalizedEvent
from whatsapp_provider.memory import (
    MAX_STORED_TEXT,
    MemoryLeakError,
    MemoryRecord,
    MemorySanitizer,
    SENSITIVE_KEYS,
    assert_no_secrets,
)


def _ev(text="oi", metadata=None, media=None):
    return NormalizedEvent(
        event_id="m1",
        provider="openwa",
        session_id="s1",
        type=EventType.MESSAGE,
        timestamp=1.0,
        chat_id="5511999999999@c.us",
        sender="5511999999999@c.us",
        text=text,
        media=media,
        metadata=metadata or {},
    )


def test_plain_text_is_preserved():
    rec = MemorySanitizer().to_record(_ev(text="oi, tudo bem?"))
    assert rec.text == "oi, tudo bem?"
    assert rec.untrusted is True
    assert rec.chat_id == "5511999999999@c.us"


def test_token_in_message_text_is_redacted():
    rec = MemorySanitizer().to_record(_ev(text="minha api_key=SUPERSECRETVALUE123 ok"))
    assert "SUPERSECRETVALUE123" not in rec.text
    assert "[REDACTED]" in rec.text


def test_qr_dataurl_in_text_is_redacted():
    payload = "olha o qr data:image/png;base64,AAAABBBBCCCCDDDDEEEEFFFFGGGGHHHH fim"
    rec = MemorySanitizer().to_record(_ev(text=payload))
    assert "base64,AAAABBBB" not in rec.text
    assert "[REDACTED]" in rec.text


def test_media_bytes_are_never_stored_only_kind():
    rec = MemorySanitizer().to_record(
        _ev(media={"mimetype": "image/png", "kind": "image", "filename": "x.png"})
    )
    assert rec.has_media is True
    assert rec.media_kind == "image"
    # nenhum campo de bytes/base64 existe no registro
    assert not hasattr(rec, "media_bytes")
    assert "base64" not in (rec.text or "")


def test_sensitive_metadata_keys_are_dropped():
    ev = _ev(metadata={"openwa_event": "onMessage", "token": "abc", "api_key": "xyz", "cookie": "c"})
    rec = MemorySanitizer().to_record(ev)
    assert rec.metadata.get("openwa_event") == "onMessage"
    assert not (set(rec.metadata) & SENSITIVE_KEYS)


def test_sensitive_value_in_nonsensitive_key_is_redacted():
    ev = _ev(metadata={"note": "token=LEAKME123 in the note"})
    rec = MemorySanitizer().to_record(ev)
    assert "LEAKME123" not in rec.metadata["note"]


def test_text_is_capped():
    rec = MemorySanitizer().to_record(_ev(text="a" * (MAX_STORED_TEXT + 500)))
    assert len(rec.text) == MAX_STORED_TEXT


def test_assert_no_secrets_rejects_dirty_record():
    dirty = MemoryRecord(
        event_id="x", session_id="s1", provider="openwa", chat_id="c", sender="s",
        kind="message", timestamp=0.0,
        text="here is data:image/png;base64,AAAABBBBCCCCDDDDEEEEFFFFGGGG leaking",
    )
    with pytest.raises(MemoryLeakError):
        assert_no_secrets(dirty)


def test_assert_no_secrets_rejects_sensitive_metadata_key():
    dirty = MemoryRecord(
        event_id="x", session_id="s1", provider="openwa", chat_id="c", sender="s",
        kind="message", timestamp=0.0, text="clean",
        metadata={"token": "abc"},
    )
    with pytest.raises(MemoryLeakError):
        assert_no_secrets(dirty)


def test_clean_record_passes_assert_no_secrets():
    rec = MemorySanitizer().to_record(_ev(text="mensagem normal", metadata={"openwa_event": "onMessage"}))
    assert_no_secrets(rec)  # não levanta


def test_provenance_untrusted_is_always_true():
    rec = MemorySanitizer().to_record(_ev())
    assert rec.untrusted is True
