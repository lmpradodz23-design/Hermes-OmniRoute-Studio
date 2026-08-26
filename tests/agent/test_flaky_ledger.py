"""Tests for the flaky-test ledger (§44)."""

from __future__ import annotations

from agent.flaky_ledger import FlakyLedger


def test_flaky_detection_across_runs():
    led = FlakyLedger()
    # 4 runs: 1 clean pass, 2 retry-passes (flaky), 1 fail
    led.record("t", passed=True)
    led.record("t", passed=True, retry_pass=True)
    led.record("t", passed=True, retry_pass=True)
    led.record("t", passed=False)
    rec = led.get("t")
    assert rec.runs == 4 and rec.retry_passes == 2
    assert led.is_flaky("t", threshold=0.2) is True
    assert "t" in led.quarantined(threshold=0.2)


def test_not_flaky_below_min_runs():
    led = FlakyLedger()
    led.record("t", passed=True, retry_pass=True)
    assert led.is_flaky("t") is False   # below min_runs


def test_stable_test_not_quarantined():
    led = FlakyLedger()
    for _ in range(5):
        led.record("stable", passed=True)
    assert led.quarantined() == ()


def test_snapshot_restore():
    led = FlakyLedger()
    for _ in range(3):
        led.record("t", passed=True, retry_pass=True)
    snap = led.snapshot()
    fresh = FlakyLedger()
    fresh.restore(snap)
    assert fresh.get("t").retry_passes == 3
