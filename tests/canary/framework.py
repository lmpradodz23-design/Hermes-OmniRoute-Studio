"""Reusable canary framework (Wave 6, §25/§116).

WAVE ZERO found several real hand-rolled break-defense canaries (the multiprocess
`update-marker.concurrency.test.ts` being the textbook one) but no shared driver.
This generalizes that pattern so every critical defense can ship an automated
break -> RED -> restore -> GREEN proof:

  GREEN  = with the real defense active, the attack is BLOCKED.
  RED    = with the defense broken *in isolation*, the same attack gets THROUGH,
           which proves the harness is strong enough to catch a regression.

A canary is only trustworthy if BOTH hold. Critically the driver is **fail-closed**:
if the "break" step cannot actually disable the defense, ``red_when_broken`` is
False and the canary FAILS — a too-weak harness can never masquerade as green
(mirrors the update-marker canary that asserts its buggy variant yields >1 winner).

An ``attack`` callable returns ``True`` when the action was BLOCKED by the defense
and ``False`` when it got through.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, ContextManager, Iterator


@dataclass(frozen=True)
class CanaryResult:
    name: str
    green: bool               # real defense blocks the attack
    red_when_broken: bool     # broken defense lets the attack through

    @property
    def ok(self) -> bool:
        return self.green and self.red_when_broken

    def describe(self) -> str:
        return (
            f"canary {self.name!r}: green(defense blocks)={self.green} "
            f"red(broken lets through)={self.red_when_broken} ok={self.ok}"
        )


@contextmanager
def _nullcontext() -> Iterator[None]:
    yield None


def run_canary(
    name: str,
    attack: Callable[[], bool],
    *,
    break_guard: Callable[[], ContextManager[object]],
    guard_active: Callable[[], ContextManager[object]] | None = None,
) -> CanaryResult:
    """Run a canary and report both halves without asserting.

    - ``attack()`` performs the guarded action and returns True iff BLOCKED.
    - ``guard_active()`` (optional) ensures the real defense is in place while we
      confirm GREEN (defaults to a no-op — the defense is assumed already active).
    - ``break_guard()`` disables the defense *in isolation* (e.g. monkeypatch,
      temporary state edit) and MUST restore it on exit.
    """
    active = guard_active or _nullcontext
    with active():
        green = bool(attack())
    with break_guard():
        blocked_while_broken = bool(attack())
    return CanaryResult(name=name, green=green, red_when_broken=not blocked_while_broken)


def assert_canary(
    name: str,
    attack: Callable[[], bool],
    *,
    break_guard: Callable[[], ContextManager[object]],
    guard_active: Callable[[], ContextManager[object]] | None = None,
) -> CanaryResult:
    """Run a canary and assert it is fully valid (raises AssertionError otherwise)."""
    result = run_canary(
        name, attack, break_guard=break_guard, guard_active=guard_active
    )
    assert result.green, (
        f"{name}: the real defense did NOT block the attack — it is not actually "
        f"protecting anything. {result.describe()}"
    )
    assert result.red_when_broken, (
        f"{name}: harness too weak — the attack was still blocked with the defense "
        f"removed, so this canary could not detect a regression. {result.describe()}"
    )
    return result


__all__ = ["CanaryResult", "run_canary", "assert_canary"]
