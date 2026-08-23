"""Validação adversarial — IDs, texto, mídia (path traversal), browser args."""

import pytest

from whatsapp_provider.validation import (
    WhatsAppValidationError,
    validate_browser_args,
    validate_chat_id,
    validate_media_path,
    validate_text,
)


@pytest.mark.parametrize("cid", ["5511999998888@c.us", "120363012345678@g.us", "status@broadcast"])
def test_valid_chat_ids(cid):
    assert validate_chat_id(cid) == cid


@pytest.mark.parametrize(
    "cid",
    [
        "5511@c.us; rm -rf /",
        "../../etc/passwd@c.us",
        "5511@c.us`whoami`",
        "5511@c.us\x00",
        "not-a-number@c.us",
        "5511@evil.us",
        "",
    ],
)
def test_malicious_chat_ids_rejected(cid):
    with pytest.raises(WhatsAppValidationError):
        validate_chat_id(cid)


def test_text_length_capped():
    with pytest.raises(WhatsAppValidationError):
        validate_text("x" * 70000)


def test_text_nul_rejected():
    with pytest.raises(WhatsAppValidationError):
        validate_text("ola\x00mundo")


def test_media_path_traversal_rejected(tmp_path):
    (tmp_path / "ok.jpg").write_bytes(b"x")
    # dentro da raiz: ok
    assert validate_media_path("ok.jpg", allowed_root=str(tmp_path)).name == "ok.jpg"
    # escape: recusado
    with pytest.raises(WhatsAppValidationError):
        validate_media_path("../../etc/passwd", allowed_root=str(tmp_path))
    with pytest.raises(WhatsAppValidationError):
        validate_media_path("/etc/passwd", allowed_root=str(tmp_path))


def test_browser_args_allowlist():
    assert validate_browser_args(["--headless", "--disable-gpu"]) == ["--headless", "--disable-gpu"]


@pytest.mark.parametrize(
    "arg",
    ["--no-sandbox", "--disable-web-security", "--remote-debugging-port=9222", "--evil-flag"],
)
def test_insecure_browser_args_rejected(arg):
    with pytest.raises(WhatsAppValidationError):
        validate_browser_args([arg])
