"""Test intelligence: diff -> impacted-test selection (Wave 4, §44).

Uses the code graph to pick the tests whose dependency closure intersects a
change. Fail-OPEN by contract: if any changed file is not covered by the graph
(so we cannot prove what it affects), select ALL tests — a mandatory gate is
never silently skipped. This mirrors the repo's existing detect-changes fail-open
CI policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from agent.code_graph import CodeGraph


@dataclass(frozen=True)
class SelectionResult:
    tests: frozenset[str]      # test *files* to run
    fail_open: bool            # True == ran everything because coverage was unknown
    reason: str


def select_impacted_tests(
    graph: CodeGraph,
    changed_files: Sequence[str],
    all_test_files: Iterable[str],
    *,
    changed_symbols: Iterable[str] | None = None,
) -> SelectionResult:
    all_tests = frozenset(all_test_files)
    if not changed_files and not changed_symbols:
        return SelectionResult(frozenset(), False, "no_changes")

    # Fail-open if any changed file is not represented in the graph.
    for f in changed_files:
        if not graph.symbols_in(f):
            return SelectionResult(all_tests, True, f"uncovered_change:{f}")

    changed_syms: set[str] = set(changed_symbols or ())
    for f in changed_files:
        changed_syms.update(graph.symbols_in(f))

    impacted_syms = graph.impacted_tests(changed_syms)
    impacted_files = frozenset(graph.symbol(s).file for s in impacted_syms) & all_tests
    return SelectionResult(impacted_files, False, "impacted_by_graph")


__all__ = ["SelectionResult", "select_impacted_tests"]
