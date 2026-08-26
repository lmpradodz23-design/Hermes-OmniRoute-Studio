"""Design + Creative contracts (Wave 3, §35/§36/§37/§38).

Formalizes the design-direction + creative-generation surface as typed contracts
so the factory can consume design/assets coherently. Does NOT create an
ImageEngineV2 — it is the contract the existing `plugins/image_gen` providers and
design skills speak, and it keeps image generation under the ABSOLUTE LOCAL_ONLY
rule: under local-only, a cloud-only image provider is BLOCKED (zero egress, no
remote fallback). Pure module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ------------------------------ Design ----------------------------------- #


@dataclass(frozen=True)
class DesignSpec:
    audience: str = ""
    palette: tuple[str, ...] = ()          # hex tokens
    typography: tuple[str, ...] = ()       # font/scale tokens
    grid: str = ""
    spacing: str = ""
    components: tuple[str, ...] = ()
    imagery: str = ""
    responsive: bool = True
    accessibility: str = "WCAG 2.2 AA"

    def is_complete(self) -> bool:
        return bool(self.audience and self.palette and self.typography)


@dataclass(frozen=True)
class BrandContext:
    palette: tuple[str, ...] = ()
    style: str = ""
    subject: str = ""
    aspect_ratio: str = "1:1"
    brand_rules: tuple[str, ...] = ()

    @classmethod
    def from_design(cls, design: DesignSpec, *, subject: str = "", aspect_ratio: str = "1:1") -> "BrandContext":
        return cls(palette=design.palette, style=design.imagery, subject=subject,
                   aspect_ratio=aspect_ratio)


# ------------------------------ Creative --------------------------------- #


class CreativeOp(str, Enum):
    GENERATE = "generate"
    EDIT = "edit"
    VARIATION = "variation"
    UPSCALE = "upscale"
    REMOVE_BACKGROUND = "remove_background"
    LOGO = "logo"
    HERO = "hero"
    MOCKUP = "mockup"
    UI_ASSET = "ui_asset"


class CreativeDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCKED_LOCAL_ONLY = "BLOCKED_LOCAL_ONLY"   # cloud provider under local-only
    DENY = "DENY"


@dataclass(frozen=True)
class CreativeRequest:
    op: CreativeOp
    prompt: str = ""
    brand: BrandContext | None = None
    reference_refs: tuple[str, ...] = ()
    local_only: bool = False
    provider_is_local: bool = False        # served by an on-device image provider


@dataclass(frozen=True)
class AssetEvidence:
    op: CreativeOp
    provider: str
    model: str
    prompt: str                     # sanitized prompt (for reproducibility)
    aspect_ratio: str = "1:1"
    asset_hash: str | None = None


@dataclass(frozen=True)
class CreativeResult:
    ok: bool
    asset_ref: str | None = None
    evidence: AssetEvidence | None = None
    denied_reason: str | None = None


def decide_creative(request: CreativeRequest) -> CreativeDecision:
    """LOCAL_ONLY is absolute for images: cloud provider under local-only is BLOCKED
    (no remote fallback)."""
    if request.local_only and not request.provider_is_local:
        return CreativeDecision.BLOCKED_LOCAL_ONLY
    return CreativeDecision.ALLOW


def build_evidence(request: CreativeRequest, *, provider: str, model: str,
                   asset_hash: str | None = None) -> AssetEvidence:
    aspect = request.brand.aspect_ratio if request.brand else "1:1"
    return AssetEvidence(op=request.op, provider=provider, model=model,
                         prompt=request.prompt, aspect_ratio=aspect, asset_hash=asset_hash)


__all__ = [
    "DesignSpec", "BrandContext", "CreativeOp", "CreativeDecision",
    "CreativeRequest", "AssetEvidence", "CreativeResult",
    "decide_creative", "build_evidence",
]
