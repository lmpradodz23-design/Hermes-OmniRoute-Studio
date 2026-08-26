"""Tests for MCP control plane (§7) and release pipeline model (§49)."""

from __future__ import annotations

from agent.mcp_control_plane import ToolHealth, ToolMeta, ToolRegistry, ToolRisk
from agent.mission_class import MissionClass
from agent.mission_evidence import EvidenceItem, EvidenceKind, Verification
from agent.release_pipeline import evaluate_release


def test_registry_selects_only_needed_healthy_tools():
    reg = ToolRegistry([
        ToolMeta("fs.read", capability="filesystem", risk=ToolRisk.LOW),
        ToolMeta("web.fetch", capability="web", risk=ToolRisk.MEDIUM),
        ToolMeta("shell.exec", capability="shell", risk=ToolRisk.HIGH),
        ToolMeta("db.down", capability="filesystem", health=ToolHealth.DOWN),
    ])
    sel = reg.select_for_mission({"filesystem"})
    assert [t.id for t in sel] == ["fs.read"]          # only needed + healthy (not the 107)
    assert reg.get("db.down").usable is False


def test_registry_respects_max_risk():
    reg = ToolRegistry([
        ToolMeta("safe", capability="c", risk=ToolRisk.LOW),
        ToolMeta("risky", capability="c", risk=ToolRisk.HIGH),
    ])
    sel = reg.select_for_mission({"c"}, max_risk=ToolRisk.MEDIUM)
    assert [t.id for t in sel] == ["safe"]


def test_release_ready_only_with_all_stage_evidence():
    # MICRO pipeline = implement/test/evidence (mandatory test+evidence).
    verdict = evaluate_release(
        MissionClass.MICRO,
        provided={
            "implement": [EvidenceItem(EvidenceKind.DIFF, "d")],
            "test": [EvidenceItem(EvidenceKind.TEST, "t")],
        },
    )
    assert verdict.ready is True


def test_release_blocked_when_a_stage_lacks_evidence():
    verdict = evaluate_release(
        MissionClass.STANDARD,   # spec/implement/test/security/evidence
        provided={
            "implement": [EvidenceItem(EvidenceKind.DIFF, "d")],
            "test": [EvidenceItem(EvidenceKind.TEST, "t")],
            # security stage evidence missing
        },
    )
    assert verdict.ready is False
    assert "security" in verdict.blocking_stages
