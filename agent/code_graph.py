"""Code / knowledge graph + impact analysis (Wave 4, §41/§42).

WAVE ZERO found no code graph and therefore no impact/blast-radius analysis (the
LSP service is wired for diagnostics only). This is the missing substrate: a
directed dependency graph of symbols (file -> symbol -> route -> api -> service
-> db -> test) with transitive dependents/dependencies, blast-radius, and
incremental per-file update (so it is refreshed by diff, not rebuilt each time).

Pure module; handles cycles. A later increment populates it from the existing
`agent/lsp` service + the per-edit delta-baseline seam.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Symbol:
    id: str                 # stable id, e.g. "app/routes.py::login"
    file: str
    kind: str = "symbol"    # module|function|class|route|api|service|db|migration|test


class CodeGraph:
    """Directed graph where an edge src->dst means 'src depends on dst'."""

    def __init__(self) -> None:
        self._sym: dict[str, Symbol] = {}
        self._out: dict[str, set[str]] = {}   # depends-on
        self._in: dict[str, set[str]] = {}    # depended-on-by (reverse)

    # ---- build / incremental update ------------------------------------ #

    def add_symbol(self, sym: Symbol) -> None:
        self._sym[sym.id] = sym
        self._out.setdefault(sym.id, set())
        self._in.setdefault(sym.id, set())

    def add_edge(self, src: str, dst: str) -> None:
        if src not in self._sym or dst not in self._sym:
            raise KeyError(f"add_edge requires known symbols: {src!r}->{dst!r}")
        self._out[src].add(dst)
        self._in[dst].add(src)

    def remove_file(self, file: str) -> None:
        """Drop all symbols in ``file`` and their edges (incremental diff update)."""
        victims = [sid for sid, s in self._sym.items() if s.file == file]
        for sid in victims:
            for dst in self._out.pop(sid, set()):
                self._in.get(dst, set()).discard(sid)
            for src in self._in.pop(sid, set()):
                self._out.get(src, set()).discard(sid)
            self._sym.pop(sid, None)

    # ---- queries -------------------------------------------------------- #

    def __contains__(self, sid: object) -> bool:
        return sid in self._sym

    def symbol(self, sid: str) -> Symbol:
        return self._sym[sid]

    def symbols_in(self, file: str) -> tuple[str, ...]:
        return tuple(sid for sid, s in self._sym.items() if s.file == file)

    def files(self) -> frozenset[str]:
        return frozenset(s.file for s in self._sym.values())

    def _reach(self, start: Iterable[str], adj: dict[str, set[str]]) -> frozenset[str]:
        seen: set[str] = set()
        q: deque[str] = deque(s for s in start if s in self._sym)
        while q:
            cur = q.popleft()
            for nxt in adj.get(cur, ()):  # cycle-safe via ``seen``
                if nxt not in seen:
                    seen.add(nxt)
                    q.append(nxt)
        return frozenset(seen)

    def dependents(self, sid: str) -> frozenset[str]:
        """Everything that (transitively) depends on ``sid`` (reverse reachability)."""
        return self._reach([sid], self._in)

    def dependencies(self, sid: str) -> frozenset[str]:
        """Everything ``sid`` (transitively) depends on (forward reachability)."""
        return self._reach([sid], self._out)

    def blast_radius(self, changed: Iterable[str]) -> frozenset[str]:
        """Changed symbols + everything that transitively depends on them (§42)."""
        changed = [c for c in changed if c in self._sym]
        radius: set[str] = set(changed)
        for c in changed:
            radius |= self.dependents(c)
        return frozenset(radius)

    def impacted_tests(self, changed: Iterable[str]) -> frozenset[str]:
        """Test symbols within the blast radius of a change."""
        return frozenset(
            sid for sid in self.blast_radius(changed) if self._sym[sid].kind == "test"
        )


__all__ = ["Symbol", "CodeGraph"]
