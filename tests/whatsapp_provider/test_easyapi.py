"""Config do runtime externo — segura por padrão, e log sem segredo."""

import pytest

from whatsapp_provider.easyapi import (
    EasyApiConfig,
    EasyApiConfigError,
    generate_api_key,
    redact_for_log,
)


def test_api_key_is_mandatory():
    with pytest.raises(EasyApiConfigError, match="apiKey"):
        EasyApiConfig(api_key="")


def test_api_key_minimum_strength():
    with pytest.raises(EasyApiConfigError):
        EasyApiConfig(api_key="short")


def test_host_must_be_loopback():
    key = generate_api_key()
    EasyApiConfig(api_key=key, host="127.0.0.1")  # ok
    with pytest.raises(EasyApiConfigError, match="loopback"):
        EasyApiConfig(api_key=key, host="0.0.0.0")  # exposto: recusado


def test_api_key_goes_in_env_not_argv():
    cfg = EasyApiConfig(api_key=generate_api_key(), session_id="test")
    argv = cfg.launch_argv()
    joined = " ".join(argv)
    assert cfg.api_key not in joined  # segredo nunca no argv (visível em ps)
    assert cfg.env()["WA_API_KEY"] == cfg.api_key
    # baseline estável v4, não v5-alpha
    assert any("4.76.0" in a for a in argv)


def test_generated_keys_are_unique_and_strong():
    a, b = generate_api_key(), generate_api_key()
    assert a != b
    assert len(a) >= 32


def test_redact_hides_secrets_in_logs():
    line = 'connecting api_key=SECRETVALUE123 token: abc123 to session'
    red = redact_for_log(line)
    assert "SECRETVALUE123" not in red
    assert "abc123" not in red
    assert "[REDACTED]" in red


def test_redact_hides_qr_datablob():
    line = "QR: data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA"
    red = redact_for_log(line)
    assert "iVBORw0KGgo" not in red
