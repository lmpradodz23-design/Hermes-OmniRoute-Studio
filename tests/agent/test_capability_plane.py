"""Unified policy tests for native and OmniRoute capability providers."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest


def _config(*, skills_mcp: bool = True) -> dict:
    return {
        "capability_plane": {
            "enabled": True,
            "mutations_require_approval": True,
            "providers": {
                "memory": {"native": True, "mcp": True},
                "skills": {"native": True, "mcp": skills_mcp},
                "plugins": {"native": True, "mcp": True},
            },
        }
    }


def test_native_and_mcp_memory_writes_share_one_approval_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agent.capability_plane import CapabilityPlane

    monkeypatch.setattr("hermes_cli.config.load_config_readonly", lambda: _config())
    plane = CapabilityPlane(home=tmp_path)

    native = plane.evaluate_tool("memory", {"action": "add", "content": "fact"})
    mcp = plane.evaluate_tool("mcp__omniroute__omniroute_memory_add", {"content": "fact"})

    assert native is not None and mcp is not None
    assert native["action"] == mcp["action"] == "approve"
    assert native["rule_key"] == mcp["rule_key"] == "capability:memory:write"


def test_disabling_mcp_skills_blocks_github_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agent.capability_plane import CapabilityPlane

    monkeypatch.setattr(
        "hermes_cli.config.load_config_readonly", lambda: _config(skills_mcp=False)
    )
    decision = CapabilityPlane(home=tmp_path).evaluate_tool(
        "github_skills_install",
        {"repository": "owner/repo"},
    )

    assert decision is not None
    assert decision["action"] == "block"
    assert "skills/mcp" in decision["message"]


def test_skill_name_conflict_is_logged_and_native_wins(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from agent.capability_plane import CapabilityPlane

    skill = tmp_path / "skills" / "shared-name"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: shared-name\n---\n", encoding="utf-8")
    monkeypatch.setattr("hermes_cli.config.load_config_readonly", lambda: _config())

    with caplog.at_level(logging.WARNING):
        decision = CapabilityPlane(home=tmp_path).evaluate_tool(
            "mcp__omniroute__omniroute_skills_execute",
            {"name": "shared-name"},
        )

    assert decision is not None
    assert decision["action"] == "block"
    assert "native" in decision["message"]
    assert "shared-name" in caplog.text


def test_core_plane_runs_through_existing_pre_tool_authorization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hermes_cli.plugins import _get_pre_tool_call_directive_details

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr("hermes_cli.config.load_config_readonly", lambda: _config())
    monkeypatch.setattr("hermes_cli.lifecycle.invoke_hook", lambda *_args, **_kwargs: [])

    directive = _get_pre_tool_call_directive_details(
        "mcp__omniroute__omniroute_memory_add",
        {"content": "fact"},
    )

    assert directive.action == "approve"
    assert directive.rule_key == "capability-plane:capability:memory:write"
