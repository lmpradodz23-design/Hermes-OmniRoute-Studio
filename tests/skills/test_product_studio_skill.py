from __future__ import annotations

from pathlib import Path
import re

import yaml

from agent.skill_utils import (
    iter_skill_index_files,
    parse_frontmatter,
    skill_matches_platform_list,
)


ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = ROOT / "skills" / "software-development" / "product-studio"
SKILL = SKILL_ROOT / "SKILL.md"
CONTRACT = SKILL_ROOT / "contracts.yaml"


def load_skill() -> tuple[dict, str]:
    return parse_frontmatter(SKILL.read_text(encoding="utf-8"))


def load_contract() -> dict:
    payload = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_product_studio_is_discoverable_on_the_running_platform() -> None:
    metadata, body = load_skill()
    discovered = list(iter_skill_index_files(SKILL_ROOT, "SKILL.md"))

    assert SKILL in discovered
    assert metadata["name"] == "product-studio"
    assert metadata["version"] == "0.4.0"
    assert skill_matches_platform_list(metadata["platforms"])
    assert body.strip()


def test_product_studio_contract_has_fail_closed_review_gates() -> None:
    contract = load_contract()
    gates = contract["review_gates"]

    assert contract["schema_version"] == 1
    assert gates["spec"] == {
        "command": "/goal draft",
        "resume_command": "/goal resume",
        "auto_execute": False,
    }
    assert gates["authenticated_browser"]["explicit_user_intent"] is True
    assert gates["production_publish"]["explicit_user_intent"] is True


def test_every_declared_reference_resolves_inside_the_skill_package() -> None:
    references = load_contract()["references"]
    assert len(references) == len(set(references))

    for name in references:
        candidate = (SKILL_ROOT / "references" / name).resolve(strict=True)
        candidate.relative_to(SKILL_ROOT.resolve())
        assert candidate.is_file()
        assert candidate.read_text(encoding="utf-8").strip()


def test_capability_contract_covers_product_types_integrations_and_specialists() -> None:
    contract = load_contract()

    assert set(contract["supported_products"]) == {"web", "desktop", "mobile", "api", "data", "ai"}
    assert set(contract["integrations"]["deployment"]) == {"supabase", "vercel"}
    assert contract["integrations"]["tools"] == ["composio"]
    assert contract["integrations"]["model_routing"] == ["omniroute"]
    assert len(set(contract["specialists"])) >= 7


def test_package_contains_no_unresolved_delivery_placeholders() -> None:
    sources = [SKILL, CONTRACT, *sorted((SKILL_ROOT / "references").glob("*.md"))]

    for source in sources:
        text = source.read_text(encoding="utf-8")
        assert re.search(r"(?im)^\s*(?:TODO|FIXME)(?:\b|:)", text) is None
        assert re.search(r"(?im)^\s*PLACEHOLDER(?:\b|:)", text) is None
