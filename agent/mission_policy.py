"""Scheduler dispatch policy: resource-governor + autonomy enforcement (§8/§9/§60).

Composes the existing budget-state roll-up and the autonomy-level gate into a
single node -> Decision callable the MissionRuntime scheduler consults before
dispatching a node. Priority: a hard budget breach or a required override wins;
otherwise the autonomy level decides based on the node's action class. Pure.
"""

from __future__ import annotations

from typing import Callable

from agent.autonomy_levels import ActionClass, AutonomyLevel, Decision, decide
from agent.budget_state import BudgetState


def make_dispatch_policy(
    *,
    autonomy: AutonomyLevel,
    action_of: Callable[[str], ActionClass],
    budget_of: Callable[[], BudgetState] | None = None,
) -> Callable[[str], Decision]:
    """Build a node_id -> Decision policy for MissionRuntime(policy=...)."""

    def policy(node_id: str) -> Decision:
        if budget_of is not None:
            b = budget_of()
            if b == BudgetState.LIMIT_REACHED:
                return Decision.DENY               # hard budget breach: do not dispatch
            if b == BudgetState.OVERRIDE_REQUIRED:
                return Decision.HUMAN_GATE          # needs authorization to spend
        return decide(autonomy, action_of(node_id))

    return policy


__all__ = ["make_dispatch_policy"]
