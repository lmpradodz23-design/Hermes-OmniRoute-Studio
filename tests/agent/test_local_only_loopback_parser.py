"""Adversarial attack on the LOCAL_ONLY loopback parser (_is_loopback_url).

Rule: only UNAMBIGUOUSLY local destinations may pass. A remote host disguised as
local must be denied. Ambiguous/exotic forms are denied (fail-closed / safe
direction) even if some client MIGHT resolve them locally — over-blocking is
safe; under-blocking (a remote leaking) is the security failure we forbid.
"""

import pytest

from agent.local_only import _is_loopback_url, egress_denial_reason


# (url, must_be_local)
GENUINE_LOCAL = [
    "http://localhost",
    "http://localhost:11434",
    "http://localhost:11434/v1",
    "http://127.0.0.1",
    "http://127.0.0.1:1234/v1",
    "http://[::1]",
    "http://[::1]:8080",
    "http://LOCALHOST",  # mixed case
    "http://127.0.0.1.",  # trailing dot
    "http://localhost.",  # trailing dot
    "http://host.docker.internal:11434",  # allowlisted local host
    "https://127.0.0.1",  # https loopback
    "127.0.0.1:11434",  # no scheme
    "localhost:11434",  # no scheme
    # userinfo is credentials; the REAL connection target is 127.0.0.1 → local.
    "http://evil.com@127.0.0.1",
    "http://user:pass@127.0.0.1:11434",
    # IPv4-mapped IPv6 of loopback genuinely IS 127.0.0.1 → local (correct).
    "http://[::ffff:127.0.0.1]",
]

DISGUISED_REMOTE_MUST_DENY = [
    "http://localhost.attacker.com",
    "http://127.0.0.1.evil.com",
    "http://localhost@evil.com",  # host is evil.com; localhost is userinfo
    "http://127.0.0.1@evil.com",  # host is evil.com
    "http://api.openai.com",
    "https://api.anthropic.com",
    "https://generativelanguage.googleapis.com",
    "http://169.254.169.254",  # cloud metadata (link-local, NOT loopback)
    "http://10.0.0.5",  # private LAN, not loopback
    "http://192.168.1.10",
    "http://0.0.0.0",  # wildcard bind addr is NOT loopback
    # IPv4-mapped IPv6 of a REMOTE address must NOT be treated as loopback.
    "http://[::ffff:93.184.216.34]",  # mapped public IP
    "http://[::ffff:169.254.169.254]",  # mapped cloud metadata
    "http://[::ffff:10.0.0.5]",  # mapped private LAN
]

# Exotic forms some clients might resolve to 127.0.0.1. We DENY them (fail-closed).
# If any of these returned True it would be an under-block risk, so assert DENY.
AMBIGUOUS_MUST_DENY = [
    "http://127.1",  # short-form some libs expand to 127.0.0.1
    "http://2130706433",  # integer form of 127.0.0.1
    "http://0x7f000001",  # hex form
    "http://0177.0.0.1",  # octal-ish
    "http://%6c%6f%63%61%6c%68%6f%73%74",  # percent-encoded 'localhost'
]


@pytest.mark.parametrize("url", GENUINE_LOCAL)
def test_genuine_local_is_loopback(url):
    assert _is_loopback_url(url) is True, url
    assert egress_denial_reason(provider="ollama", base_url=url) == "", url


@pytest.mark.parametrize("url", DISGUISED_REMOTE_MUST_DENY)
def test_disguised_remote_is_denied(url):
    assert _is_loopback_url(url) is False, url
    assert egress_denial_reason(provider="x", base_url=url) != "", url


@pytest.mark.parametrize("url", AMBIGUOUS_MUST_DENY)
def test_ambiguous_forms_fail_closed(url):
    # Safe direction: deny. (Never assert True here — that would permit a form
    # whose true target we cannot verify.)
    assert _is_loopback_url(url) is False, url
    assert egress_denial_reason(provider="x", base_url=url) != "", url


def test_empty_and_malformed_are_denied():
    for bad in ["", "   ", None, "not a url", "http://", "://nohost", "ftp://api.evil.com"]:
        assert _is_loopback_url(bad) is False, bad
