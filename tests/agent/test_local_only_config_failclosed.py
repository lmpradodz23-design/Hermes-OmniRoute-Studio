"""LOCAL_ONLY — config_local_only_enabled must FAIL CLOSED on unknown state.

security.local_only is a critical privacy preference: a corrupt/unreadable
persisted config (or a merge path that drops the user's value) must NOT silently
turn the boundary off. A genuine fresh install (no config file) still defaults
OFF so it is not broken.
"""

from pathlib import Path

import pytest

import agent.local_only as lo


@pytest.fixture
def cfg_env(tmp_path, monkeypatch):
    """Point hermes_cli.config.get_config_path at a temp file we control, and
    let load_config be monkeypatched per test."""
    import hermes_cli.config as hc

    path = tmp_path / "config.yaml"
    monkeypatch.setattr(hc, "get_config_path", lambda: path, raising=False)
    return hc, path


def test_fresh_install_no_config_is_off(cfg_env, monkeypatch):
    hc, path = cfg_env
    assert not path.exists()
    monkeypatch.setattr(hc, "load_config", lambda: {})  # defaults
    assert lo.config_local_only_enabled() is False


def test_valid_config_on_is_on(cfg_env, monkeypatch):
    hc, path = cfg_env
    path.write_text("security:\n  local_only: true\n", encoding="utf-8")
    monkeypatch.setattr(hc, "load_config", lambda: {"security": {"local_only": True}})
    assert lo.config_local_only_enabled() is True


def test_valid_config_off_is_off(cfg_env, monkeypatch):
    hc, path = cfg_env
    path.write_text("security:\n  local_only: false\n", encoding="utf-8")
    monkeypatch.setattr(hc, "load_config", lambda: {"security": {"local_only": False}})
    assert lo.config_local_only_enabled() is False


def test_corrupt_config_fails_closed(cfg_env, monkeypatch):
    # A present-but-unparseable config → UNKNOWN security state → deny egress.
    hc, path = cfg_env
    path.write_text("security:\n  local_only: true\n  : : broken yaml [[[\n", encoding="utf-8")
    # Real load_config returns defaults on corrupt YAML (no last-known-good),
    # which would drop local_only → False. Simulate that.
    monkeypatch.setattr(hc, "load_config", lambda: {})
    assert lo.config_local_only_enabled() is True, "corrupt config must fail closed (deny)"


def test_unreadable_config_fails_closed(cfg_env, monkeypatch):
    hc, path = cfg_env
    path.write_text("security:\n  local_only: true\n", encoding="utf-8")
    monkeypatch.setattr(hc, "load_config", lambda: {})

    real_read = Path.read_text

    def _boom(self, *a, **k):
        if self == path:
            raise OSError("unreadable")
        return real_read(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", _boom)
    assert lo.config_local_only_enabled() is True, "unreadable config must fail closed"


def test_merge_dropped_value_recovered_from_raw(cfg_env, monkeypatch):
    # load_config drops the value (e.g. overlay/LKG path) but the persisted file
    # says ON → the raw cross-check must recover ON (not silently off).
    hc, path = cfg_env
    path.write_text("security:\n  local_only: true\n", encoding="utf-8")
    monkeypatch.setattr(hc, "load_config", lambda: {})  # dropped
    assert lo.config_local_only_enabled() is True


def test_empty_config_file_is_off(cfg_env, monkeypatch):
    hc, path = cfg_env
    path.write_text("", encoding="utf-8")
    monkeypatch.setattr(hc, "load_config", lambda: {})
    assert lo.config_local_only_enabled() is False


def test_load_config_raises_but_raw_on(cfg_env, monkeypatch):
    hc, path = cfg_env
    path.write_text("security:\n  local_only: true\n", encoding="utf-8")

    def _raise():
        raise RuntimeError("load exploded")

    monkeypatch.setattr(hc, "load_config", _raise)
    assert lo.config_local_only_enabled() is True


def test_malformed_top_level_fails_closed(cfg_env, monkeypatch):
    # A YAML that parses to a non-dict (e.g. a bare list) is malformed → unknown.
    hc, path = cfg_env
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    monkeypatch.setattr(hc, "load_config", lambda: {})
    assert lo.config_local_only_enabled() is True
