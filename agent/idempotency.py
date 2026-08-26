"""Mission idempotency (Wave 1, §20).

A node with a side effect (send a message, deploy, mutate a DB, a git action,
a payment-like external op) must not duplicate that effect on crash/retry. This
provides operation keys + an idempotency store that returns the cached result
for an already-completed operation instead of re-running it. Pure/in-memory core
(the caller can back it with the durable MissionStore); no secrets stored.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class OperationKey:
    mission_id: str
    node_id: str
    operation_id: str    # stable id for the *logical* side effect (not the attempt)

    def key(self) -> str:
        return f"{self.mission_id}\x1f{self.node_id}\x1f{self.operation_id}"


class IdempotencyStore:
    """Records completed side effects so a retry does not repeat them."""

    def __init__(self) -> None:
        self._done: dict[str, Any] = {}

    def is_done(self, op: OperationKey) -> bool:
        return op.key() in self._done

    def result_for(self, op: OperationKey) -> Any:
        return self._done.get(op.key())

    def record(self, op: OperationKey, result: Any = None) -> None:
        self._done[op.key()] = result

    def snapshot(self) -> Mapping[str, Any]:
        return dict(self._done)

    def restore(self, data: Mapping[str, Any]) -> None:
        self._done.update(data)


@dataclass(frozen=True)
class GuardResult:
    result: Any
    executed: bool     # False == returned the cached result (side effect skipped)


def run_once(
    store: IdempotencyStore,
    op: OperationKey,
    side_effect: Callable[[], Any],
) -> GuardResult:
    """Execute ``side_effect`` at most once per operation key.

    On a retry of an already-completed operation the cached result is returned
    and the side effect is NOT run again (dedup/idempotency). If the side effect
    raises, nothing is recorded, so a later retry can try again.
    """
    if store.is_done(op):
        return GuardResult(store.result_for(op), executed=False)
    result = side_effect()          # may raise -> not recorded -> retryable
    store.record(op, result)
    return GuardResult(result, executed=True)


__all__ = ["OperationKey", "IdempotencyStore", "GuardResult", "run_once"]
