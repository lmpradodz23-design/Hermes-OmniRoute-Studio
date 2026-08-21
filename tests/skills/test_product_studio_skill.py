from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "software-development" / "product-studio" / "SKILL.md"


def load_skill() -> tuple[dict, str]:
    text = SKILL.read_text(encoding="utf-8")
    _, frontmatter, body = text.split("---", 2)
    return yaml.safe_load(frontmatter), body


def test_product_studio_metadata_is_loadable() -> None:
    metadata, body = load_skill()

    assert metadata["name"] == "product-studio"
    assert metadata["description"].endswith(".")
    assert len(metadata["description"]) <= 60
    assert metadata["platforms"] == ["linux", "macos", "windows"]
    assert body.strip()


def test_product_studio_requires_evidence_and_browser_consent() -> None:
    _, body = load_skill()

    assert "Never call local compilation production proof" in body
    assert "Require explicit user intent before sensitive browser actions" in body
    assert "unit or integration tests" in body
    assert "end-to-end" in body


def test_product_studio_references_ship_with_the_skill() -> None:
    _, body = load_skill()

    for name in (
        "delivery-gates.md",
        "browser-security.md",
        "multi-agent-orchestration.md",
        "spec-driven-delivery.md",
        "knowledge-and-rules.md",
        "task-report.md",
        "nontechnical-intake.md",
    ):
        assert name in body
        assert (SKILL.parent / "references" / name).is_file()


def test_multi_agent_reference_uses_real_hermes_capabilities() -> None:
    reference = (SKILL.parent / "references" / "multi-agent-orchestration.md").read_text(encoding="utf-8")

    assert "delegate_task" in reference
    assert "Named Hermes bots" in reference
    assert "UI Architect" in reference
    assert "Security and Privacy Engineer" in reference
    assert "AI and Agent Architect" in reference
    assert "Do not spin up the full roster" in reference


def test_product_studio_has_reviewable_specs_live_preview_and_scoped_knowledge() -> None:
    _, body = load_skill()

    assert "/goal draft" in body
    assert "/goal resume" in body
    assert "embedded preview" in body
    assert "Knowledge Cards" in body
    assert "hierarchical `AGENTS.md`" in body

    spec = (SKILL.parent / "references" / "spec-driven-delivery.md").read_text(encoding="utf-8")
    knowledge = (SKILL.parent / "references" / "knowledge-and-rules.md").read_text(encoding="utf-8")
    report = (SKILL.parent / "references" / "task-report.md").read_text(encoding="utf-8")
    assert "awaiting-spec-review" in spec
    assert "AGENTS.override.md" in knowledge
    assert "Auto-commit" not in report
    assert "commit, push, publish, or deploy only as a separate authorized action" in report


def test_nontechnical_users_are_not_forced_to_choose_engineering_tools() -> None:
    intake = (SKILL.parent / "references" / "nontechnical-intake.md").read_text(encoding="utf-8")

    assert "make a CRM" in intake
    assert "Never ask the user to choose a framework" in intake
    assert "embedded live preview" in intake
    assert "multi-gigabyte SDKs" in intake
