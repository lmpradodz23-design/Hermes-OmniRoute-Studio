"""Tests for design + creative contracts (§35/§36/§37)."""

from __future__ import annotations

from agent.creative_contract import (
    BrandContext,
    CreativeDecision,
    CreativeOp,
    CreativeRequest,
    DesignSpec,
    build_evidence,
    decide_creative,
)


def test_design_completeness_and_brand_from_design():
    d = DesignSpec(audience="clinics", palette=("#0af", "#111"), typography=("Inter/48",))
    assert d.is_complete()
    b = BrandContext.from_design(d, subject="hero", aspect_ratio="16:9")
    assert b.palette == ("#0af", "#111") and b.aspect_ratio == "16:9"


def test_local_only_blocks_cloud_image_provider():
    req = CreativeRequest(CreativeOp.GENERATE, "a logo", local_only=True, provider_is_local=False)
    assert decide_creative(req) is CreativeDecision.BLOCKED_LOCAL_ONLY   # no remote fallback


def test_local_only_allows_local_provider():
    req = CreativeRequest(CreativeOp.GENERATE, "a logo", local_only=True, provider_is_local=True)
    assert decide_creative(req) is CreativeDecision.ALLOW


def test_non_local_only_allows_cloud():
    req = CreativeRequest(CreativeOp.UPSCALE, "x", local_only=False, provider_is_local=False)
    assert decide_creative(req) is CreativeDecision.ALLOW


def test_all_ops_present():
    assert {o.value for o in CreativeOp} >= {
        "generate", "edit", "variation", "upscale", "remove_background",
        "logo", "hero", "mockup", "ui_asset",
    }


def test_evidence_carries_reproducibility_context():
    req = CreativeRequest(CreativeOp.HERO, "sunset clinic",
                          brand=BrandContext(aspect_ratio="16:9"))
    ev = build_evidence(req, provider="fal", model="flux", asset_hash="deadbeef")
    assert ev.op is CreativeOp.HERO and ev.provider == "fal"
    assert ev.aspect_ratio == "16:9" and ev.prompt == "sunset clinic"
