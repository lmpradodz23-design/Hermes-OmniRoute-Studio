"""Self-test for the canary framework (tests/canary/framework.py).

Proves the driver (a) validates a genuine defense (GREEN + RED) and (b) is
fail-closed: a too-weak "break" that does not actually disable the defense is
reported as NOT ok, so a canary can never green-wash.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from tests.canary.framework import assert_canary, run_canary


class _Denylist:
    """A toy critical defense: block destructive commands on a denylist."""

    def __init__(self) -> None:
        self.blocked = {"rm -rf /", "format C:"}

    def attempt(self, command: str) -> bool:
        """Return True if the command was BLOCKED by the defense."""
        return command in self.blocked


def test_genuine_defense_passes_canary():
    guard = _Denylist()

    @contextmanager
    def break_guard():
        saved = set(guard.blocked)
        guard.blocked.clear()  # disable the defense in isolation
        try:
            yield
        finally:
            guard.blocked = saved  # restore

    result = assert_canary(
        "denylist:rm-rf-root",
        attack=lambda: guard.attempt("rm -rf /"),
        break_guard=break_guard,
    )
    assert result.ok
    # defense restored after the canary
    assert guard.attempt("rm -rf /") is True


def test_too_weak_break_is_reported_not_ok():
    # A "break" that changes nothing must NOT pass — the framework is fail-closed.
    guard = _Denylist()

    @contextmanager
    def noop_break():
        yield  # pretends to break, but the defense stays active

    result = run_canary(
        "denylist:weak-harness",
        attack=lambda: guard.attempt("rm -rf /"),
        break_guard=noop_break,
    )
    assert result.green is True
    assert result.red_when_broken is False
    assert result.ok is False

    # ...and assert_canary raises on such a harness rather than passing.
    with pytest.raises(AssertionError):
        assert_canary(
            "denylist:weak-harness",
            attack=lambda: guard.attempt("rm -rf /"),
            break_guard=noop_break,
        )


def test_defense_that_does_not_block_fails_green():
    # If the "defense" never blocks, GREEN is false -> canary fails.
    guard = _Denylist()
    guard.blocked.clear()  # defense is absent from the start

    @contextmanager
    def break_guard():
        yield

    with pytest.raises(AssertionError):
        assert_canary(
            "denylist:absent-defense",
            attack=lambda: guard.attempt("rm -rf /"),
            break_guard=break_guard,
        )
