"""Learned routing — history ledger + eligibility-gated scoring (Wave 6, §6/§7).

WAVE ZERO found OmniRoute routing is static/user-configured: `moa_trace.py` records
per-model cost but nothing consumes it. This adds the missing feedback substrate —
a minimal per-(task_type, model) history ledger and a scoring/selection policy —
with two hard rules the mission demands:

  1. **Privacy has absolute precedence.** Under LOCAL_ONLY a remote provider is
     ELIGIBLE=false regardless of how good its history is. Eligibility is a gate
     applied BEFORE any score; history can never override it.
  2. **History does not solely dominate.** Unbenchmarked models get a neutral
     prior so a good-but-new model is not starved by an over-fit history.

Pure module (stdlib only). Persistence is left to the caller (e.g. the existing
moa-trace/kanban SQLite path); this holds the logic and an in-memory ledger.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence


@dataclass(frozen=True)
class RouteRecord:
    task_type: str
    model: str
    provider: str
    success: bool
    verification_score: float = 0.0   # 0..1, from the evidence/verify layer
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    tokens: int = 0
    retries: int = 0
    failure_type: str | None = None
    privacy_policy: str = "any"        # "any" | "local_only"


@dataclass(frozen=True)
class RouteStats:
    n: int
    success_rate: float
    mean_score: float
    mean_latency_ms: float
    mean_cost_usd: float


@dataclass(frozen=True)
class Candidate:
    model: str
    provider: str
    is_local: bool           # served by a local/loopback provider
    capability_ok: bool = True   # can do the task at required quality
    available: bool = True       # healthy / not quarantined


@dataclass(frozen=True)
class ScoreWeights:
    success: float = 1.0
    verification: float = 1.0
    latency: float = 0.3
    cost: float = 0.3


DEFAULT_WEIGHTS = ScoreWeights()
MIN_SAMPLES_FOR_HISTORY = 3
NEUTRAL_PRIOR = 0.6   # optimistic-ish prior so new models are explored, not starved


class RouteHistory:
    """In-memory per-(task_type, model) ledger with aggregate stats."""

    def __init__(self, records: Iterable[RouteRecord] = ()):
        self._records: list[RouteRecord] = list(records)

    def record(self, rec: RouteRecord) -> None:
        self._records.append(rec)

    def __len__(self) -> int:
        return len(self._records)

    def for_key(self, task_type: str, model: str) -> list[RouteRecord]:
        return [
            r for r in self._records if r.task_type == task_type and r.model == model
        ]

    def stats(self, task_type: str, model: str) -> RouteStats:
        rows = self.for_key(task_type, model)
        n = len(rows)
        if n == 0:
            return RouteStats(0, 0.0, 0.0, 0.0, 0.0)
        succ = sum(1 for r in rows if r.success) / n
        score = sum(r.verification_score for r in rows) / n
        lat = sum(r.latency_ms for r in rows) / n
        cost = sum(r.cost_usd for r in rows) / n
        return RouteStats(n, succ, score, lat, cost)


def is_eligible(candidate: Candidate, *, local_only: bool) -> bool:
    """Hard gate applied BEFORE scoring (privacy has absolute precedence)."""
    if not candidate.capability_ok or not candidate.available:
        return False
    if local_only and not candidate.is_local:
        return False   # remote provider under LOCAL_ONLY: never eligible
    return True


def _norm(value: float, worst: float) -> float:
    """Normalize a cost/latency to 0..1 (0 = best). ``worst`` is the max seen."""
    if worst <= 0:
        return 0.0
    return max(0.0, min(1.0, value / worst))


def score_candidate(
    candidate: Candidate,
    history: RouteHistory,
    *,
    task_type: str,
    worst_latency_ms: float,
    worst_cost_usd: float,
    weights: ScoreWeights = DEFAULT_WEIGHTS,
    min_samples: int = MIN_SAMPLES_FOR_HISTORY,
) -> float:
    """Blend historical success/score with latency/cost penalties.

    Below ``min_samples`` observations the model uses a neutral prior for its
    success/score terms so it is explored rather than dominated by history.
    """
    st = history.stats(task_type, candidate.model)
    if st.n >= min_samples:
        succ = st.success_rate
        score = st.mean_score
        lat = _norm(st.mean_latency_ms, worst_latency_ms)
        cost = _norm(st.mean_cost_usd, worst_cost_usd)
    else:
        succ = NEUTRAL_PRIOR
        score = NEUTRAL_PRIOR
        lat = 0.0   # unknown cost/latency treated as neutral, not penalized
        cost = 0.0
    return (
        weights.success * succ
        + weights.verification * score
        - weights.latency * lat
        - weights.cost * cost
    )


@dataclass(frozen=True)
class RouteDecision:
    model: str | None
    provider: str | None
    score: float
    eligible_count: int
    reason: str


def select(
    candidates: Sequence[Candidate],
    history: RouteHistory,
    *,
    task_type: str,
    local_only: bool,
    weights: ScoreWeights = DEFAULT_WEIGHTS,
    min_samples: int = MIN_SAMPLES_FOR_HISTORY,
) -> RouteDecision:
    """Pick the best ELIGIBLE candidate. Eligibility (privacy/capability/health)
    is enforced first; scoring only ranks among the eligible set."""
    eligible = [c for c in candidates if is_eligible(c, local_only=local_only)]
    if not eligible:
        return RouteDecision(None, None, float("-inf"), 0, "no_eligible_candidate")
    worst_lat = max(
        (history.stats(task_type, c.model).mean_latency_ms for c in eligible), default=0.0
    )
    worst_cost = max(
        (history.stats(task_type, c.model).mean_cost_usd for c in eligible), default=0.0
    )
    best: Candidate | None = None
    best_score = float("-inf")
    for c in eligible:
        s = score_candidate(
            c, history, task_type=task_type,
            worst_latency_ms=worst_lat, worst_cost_usd=worst_cost,
            weights=weights, min_samples=min_samples,
        )
        if s > best_score:
            best_score, best = s, c
    assert best is not None
    return RouteDecision(
        best.model, best.provider, best_score, len(eligible),
        "selected_by_history" if len(history) else "selected_by_prior",
    )


__all__ = [
    "RouteRecord", "RouteStats", "Candidate", "ScoreWeights",
    "RouteHistory", "RouteDecision",
    "is_eligible", "score_candidate", "select",
    "DEFAULT_WEIGHTS", "MIN_SAMPLES_FOR_HISTORY", "NEUTRAL_PRIOR",
]
