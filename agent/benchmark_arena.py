"""Benchmark Arena (Wave 6, §52).

Aggregates the learned-routing history (agent.route_history.RouteRecord) into
per-(task_type, model) benchmark scores so routing learns from evidence rather
than marketing. Reuses the existing route-history records; adds verified-rate,
intervention rate, and a composite score + ranking. Pure module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from agent.route_history import RouteRecord


@dataclass(frozen=True)
class BenchmarkScore:
    task_type: str
    model: str
    n: int
    completion_rate: float      # success / n
    verified_rate: float        # mean verification_score
    mean_latency_ms: float
    mean_cost_usd: float
    intervention_rate: float    # mean retries (proxy for human/agent intervention)

    @property
    def composite(self) -> float:
        # higher is better: reward verified completion, lightly penalize retries.
        return (
            0.6 * self.completion_rate
            + 0.4 * self.verified_rate
            - 0.1 * min(1.0, self.intervention_rate)
        )


def score(records: Iterable[RouteRecord], task_type: str, model: str) -> BenchmarkScore | None:
    rows = [r for r in records if r.task_type == task_type and r.model == model]
    n = len(rows)
    if n == 0:
        return None
    return BenchmarkScore(
        task_type=task_type, model=model, n=n,
        completion_rate=sum(1 for r in rows if r.success) / n,
        verified_rate=sum(r.verification_score for r in rows) / n,
        mean_latency_ms=sum(r.latency_ms for r in rows) / n,
        mean_cost_usd=sum(r.cost_usd for r in rows) / n,
        intervention_rate=sum(r.retries for r in rows) / n,
    )


def rank_models(records: Iterable[RouteRecord], task_type: str) -> list[BenchmarkScore]:
    recs = list(records)
    models = sorted({r.model for r in recs if r.task_type == task_type})
    scored = [s for m in models if (s := score(recs, task_type, m)) is not None]
    scored.sort(key=lambda s: s.composite, reverse=True)
    return scored


__all__ = ["BenchmarkScore", "score", "rank_models"]
