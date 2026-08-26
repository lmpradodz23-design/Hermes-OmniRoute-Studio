"""Free-first provider routing (§16/§18/§19/§28) — an OmniRoute selection layer.

Applies the mandatory priority order and never inverts it:
  1. policy/security (caller pre-filters)  2. LOCAL_ONLY / privacy (ABSOLUTE)
  3. required capability  4. availability  5. quality history  6. free-tier pref
  7. cost (paid needs authorization — cost guard)  8. latency
Profiles: FREE_FIRST / LOCAL_FIRST / QUALITY_FIRST / BALANCED / CUSTOM. Pure module;
extends OmniRoute (not a parallel router). Quality comes from the Benchmark Arena.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from agent.provider_catalog import Capability, ProviderEntry, Tri


class RoutingProfile(str, Enum):
    FREE_FIRST = "FREE_FIRST"
    LOCAL_FIRST = "LOCAL_FIRST"
    QUALITY_FIRST = "QUALITY_FIRST"
    BALANCED = "BALANCED"
    CUSTOM = "CUSTOM"


@dataclass(frozen=True)
class ProviderCandidate:
    entry: ProviderEntry
    connected: bool = True
    healthy: bool = True
    free_quota_exhausted: bool = False
    quality_score: float = 0.6        # from benchmark arena (neutral prior default)
    latency_ms: float = 0.0

    @property
    def is_free_or_local(self) -> bool:
        if self.entry.is_local:
            return True
        return self.entry.free_tier == Tri.YES and not self.free_quota_exhausted

    @property
    def is_paid(self) -> bool:
        return not self.is_free_or_local

    @property
    def eligible_base(self) -> bool:
        return self.connected and self.healthy


@dataclass(frozen=True)
class RoutingDecision:
    provider_id: str | None
    reason: str
    requires_paid_confirmation: bool = False


def _tier_rank(c: ProviderCandidate, profile: RoutingProfile) -> int:
    """Lower rank = more preferred (before quality sort)."""
    local = c.entry.is_local
    free = c.is_free_or_local and not local
    if profile == RoutingProfile.LOCAL_FIRST:
        return 0 if local else (1 if free else 2)
    if profile == RoutingProfile.FREE_FIRST:
        return 0 if c.is_free_or_local else 1
    if profile == RoutingProfile.QUALITY_FIRST:
        return 0            # quality dominates; cost-guard still applies below
    # BALANCED / CUSTOM: prefer free-or-local, paid last
    return 0 if c.is_free_or_local else 1


def select_provider(
    candidates: Sequence[ProviderCandidate],
    *,
    task_capability: Capability,
    local_only: bool,
    profile: RoutingProfile = RoutingProfile.BALANCED,
    paid_authorized: bool = False,
) -> RoutingDecision:
    # 2 privacy (ABSOLUTE) + 3 capability + 4 availability
    eligible = [
        c for c in candidates
        if c.eligible_base
        and c.entry.has(task_capability)
        and (c.entry.is_local if local_only else True)
    ]
    if not eligible:
        return RoutingDecision(None, "no_eligible_provider (privacy/capability/health)")

    # 5 quality, 6 free-tier tier, 8 latency -> order
    eligible.sort(key=lambda c: (_tier_rank(c, profile), -c.quality_score, c.latency_ms))

    # 7 cost guard: if the best choice is paid and not authorized, do NOT call it.
    best = eligible[0]
    if best.is_paid and not paid_authorized:
        # is there any free/local eligible to fall back to? (§18 fallback)
        free_alt = [c for c in eligible if not c.is_paid]
        if free_alt:
            free_alt.sort(key=lambda c: (_tier_rank(c, profile), -c.quality_score, c.latency_ms))
            return RoutingDecision(free_alt[0].entry.id, "selected_free_fallback")
        return RoutingDecision(None, "paid_confirmation_required (cost guard)",
                               requires_paid_confirmation=True)

    return RoutingDecision(best.entry.id, "selected")


__all__ = ["RoutingProfile", "ProviderCandidate", "RoutingDecision", "select_provider"]
