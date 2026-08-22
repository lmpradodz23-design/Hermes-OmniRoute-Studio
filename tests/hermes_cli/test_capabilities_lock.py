"""Fail-closed integrity tests for user-approved Hermes capabilities."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest


def _skill(home: Path, name: str = "product-studio") -> Path:
    skill = home / "skills" / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: product-studio\nversion: 0.2.0\n---\nTrusted instructions.\n",
        encoding="utf-8",
    )
    return skill


def test_one_byte_skill_change_is_blocked_before_prompt_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agent.prompt_builder import (
        build_skills_system_prompt,
        clear_skills_system_prompt_cache,
    )
    from hermes_cli.capabilities_lock import (
        CapabilityIntegrityError,
        build_snapshot,
        save_lock,
    )

    home = tmp_path / "hermes"
    skill = _skill(home)
    monkeypatch.setenv("HERMES_HOME", str(home))
    save_lock(build_snapshot(home=home, mcp_servers={}), home=home)

    clear_skills_system_prompt_cache(clear_snapshot=True)
    assert "product-studio" in build_skills_system_prompt()
    with (skill / "SKILL.md").open("a", encoding="utf-8") as handle:
        handle.write("x")

    with pytest.raises(CapabilityIntegrityError, match="product-studio.*hash mismatch"):
        build_skills_system_prompt()


def test_update_prints_diff_before_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from hermes_cli.capabilities_cmd import cmd_capabilities

    home = tmp_path / "hermes"
    _skill(home)
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    args = argparse.Namespace(capabilities_action="update", yes=False)
    assert cmd_capabilities(args) == 1
    output = capsys.readouterr().out
    assert "+ capability lock v1" in output
    assert "+ skill product-studio" in output
    assert not (home / "capabilities.lock").exists()

    args.yes = True
    assert cmd_capabilities(args) == 0
    assert (home / "capabilities.lock").exists()


def test_mcp_command_file_change_is_rejected(tmp_path: Path) -> None:
    from hermes_cli.capabilities_lock import (
        CapabilityIntegrityError,
        build_snapshot,
        save_lock,
        verify_capabilities_lock,
    )

    home = tmp_path / "hermes"
    bridge = tmp_path / "bridge.mjs"
    bridge.write_text("export {};\n", encoding="utf-8")
    servers = {"omniroute": {"command": "node", "args": [str(bridge)]}}
    save_lock(build_snapshot(home=home, mcp_servers=servers), home=home)
    bridge.write_text("export const changed = true;\n", encoding="utf-8")

    with pytest.raises(CapabilityIntegrityError, match="omniroute.*hash mismatch"):
        verify_capabilities_lock(home=home, categories={"mcp_servers"}, mcp_servers=servers)


def test_unapproved_plugin_is_rejected_before_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hermes_cli.capabilities_lock import (
        CapabilityIntegrityError,
        build_snapshot,
        save_lock,
    )
    from hermes_cli.plugins import PluginManager

    home = tmp_path / "hermes"
    monkeypatch.setenv("HERMES_HOME", str(home))
    save_lock(build_snapshot(home=home, mcp_servers={}), home=home)
    plugin = home / "plugins" / "unreviewed"
    plugin.mkdir(parents=True)
    (plugin / "plugin.yaml").write_text("name: unreviewed\n", encoding="utf-8")
    (plugin / "__init__.py").write_text("raise RuntimeError('must not import')\n", encoding="utf-8")

    with pytest.raises(CapabilityIntegrityError, match="unreviewed.*not approved"):
        PluginManager(scope_key=str(home)).discover_and_load()


def test_refreshing_skills_preserves_external_plugin_and_mcp_records(tmp_path: Path) -> None:
    from hermes_cli.capabilities_lock import load_lock, refresh_skill_records, save_lock

    home = tmp_path / "hermes"
    _skill(home)
    original = {
        "version": 1,
        "skills": [],
        "plugins": [{"id": "studio", "sha256": "kept", "path": "external"}],
        "mcp_servers": [{"id": "omniroute", "command_sha256": "kept"}],
    }
    save_lock(original, home=home)
    refresh_skill_records(home=home)
    refreshed = load_lock(home=home)

    assert refreshed is not None
    assert refreshed["plugins"] == original["plugins"]
    assert refreshed["mcp_servers"] == original["mcp_servers"]
    assert refreshed["skills"][0]["id"] == "product-studio"
