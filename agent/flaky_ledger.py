"""Flaky-test history ledger (Wave 4, §44).

WAVE ZERO found flakiness is detected per-run but never tracked across runs. This
is the durable-able ledger: it accumulates pass/fail/retry-pass history per test
and flags flaky tests for triage. It NEVER causes a mandatory test to be skipped
— quarantine is a triage signal, not a gate bypass. Pure/in-memory core with
snapshot/restore.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass
class FlakyRecord:
    test_id: str
    passes: int = 0
    fails: int = 0
    retry_passes: int = 0   # passed only on a re-run after a fail (the flaky signal)

    @property
    def runs(self) -> int:
        return self.passes + self.fails

    @property
    def flip_rate(self) -> float:
        return (self.retry_passes / self.runs) if self.runs else 0.0


class FlakyLedger:
    def __init__(self) -> None:
        self._records: dict[str, FlakyRecord] = {}

    def record(self, test_id: str, *, passed: bool, retry_pass: bool = False) -> None:
        rec = self._records.setdefault(test_id, FlakyRecord(test_id))
        if passed:
            rec.passes += 1
            if retry_pass:
                rec.retry_passes += 1
        else:
            rec.fails += 1

    def get(self, test_id: str) -> FlakyRecord | None:
        return self._records.get(test_id)

    def is_flaky(self, test_id: str, *, threshold: float = 0.2, min_runs: int = 3) -> bool:
        rec = self._records.get(test_id)
        if rec is None or rec.runs < min_runs:
            return False
        return rec.flip_rate >= threshold

    def quarantined(self, *, threshold: float = 0.2, min_runs: int = 3) -> tuple[str, ...]:
        """Tests flagged flaky for triage (NOT auto-skipped from mandatory gates)."""
        return tuple(sorted(
            t for t in self._records
            if self.is_flaky(t, threshold=threshold, min_runs=min_runs)
        ))

    def snapshot(self) -> Mapping[str, dict[str, int]]:
        return {t: {"passes": r.passes, "fails": r.fails, "retry_passes": r.retry_passes}
                for t, r in self._records.items()}

    def restore(self, data: Mapping[str, Mapping[str, int]]) -> None:
        for t, d in data.items():
            self._records[t] = FlakyRecord(t, int(d.get("passes", 0)),
                                           int(d.get("fails", 0)), int(d.get("retry_passes", 0)))


__all__ = ["FlakyRecord", "FlakyLedger"]
