"""Mission DAG primitives — a pure dependency-graph reader (Wave 1, §7).

The Autonomy Kernel already has a real dependency graph (Kanban parent edges in
``hermes_cli/kanban_db.py``) and a claim-based parallel dispatcher, but it has
**no critical-path / scheduling view** over those edges (WAVE ZERO finding). This
module is that missing read-only view, kept as a standalone, side-effect-free
utility so it can be fed by Kanban parent edges *or* Goal sub-nodes without
touching either engine.

It computes: topological order, the ready/blocked frontier for a given "done"
set, the weighted critical path (longest path = the schedule's lower bound), and
ancestor/descendant sets (the substrate a later blast-radius/impact view needs).
Nothing here mutates state or does I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping


class DagError(ValueError):
    """Raised for structural problems (unknown parent, cycle)."""


@dataclass(frozen=True)
class DagNode:
    """One mission node. ``weight`` is an estimated cost/duration (>= 0)."""

    id: str
    parents: tuple[str, ...] = ()
    weight: float = 1.0
    label: str = ""


@dataclass(frozen=True)
class CriticalPath:
    nodes: tuple[str, ...]
    weight: float


class MissionDag:
    """An immutable read-only view over a set of :class:`DagNode`."""

    def __init__(self, nodes: Iterable[DagNode]):
        self._nodes: dict[str, DagNode] = {}
        for node in nodes:
            if node.id in self._nodes:
                raise DagError(f"duplicate node id: {node.id!r}")
            if node.weight < 0:
                raise DagError(f"node {node.id!r} has negative weight")
            self._nodes[node.id] = node
        # Validate parents exist.
        for node in self._nodes.values():
            for parent in node.parents:
                if parent not in self._nodes:
                    raise DagError(
                        f"node {node.id!r} references unknown parent {parent!r}"
                    )
        # Children adjacency.
        self._children: dict[str, list[str]] = {nid: [] for nid in self._nodes}
        for node in self._nodes.values():
            for parent in node.parents:
                self._children[parent].append(node.id)
        # A topological order (also proves acyclicity).
        self._topo = self._compute_topo()

    # ---- construction helpers ------------------------------------------- #

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Mapping[str, object]]) -> "MissionDag":
        """Build from ``{id: {parents:[...], weight: n, label: s}}``."""
        nodes = []
        for nid, spec in mapping.items():
            parents = tuple(str(p) for p in (spec.get("parents") or ()))  # type: ignore[union-attr]
            weight = float(spec.get("weight", 1.0))  # type: ignore[arg-type]
            label = str(spec.get("label", ""))  # type: ignore[arg-type]
            nodes.append(DagNode(id=nid, parents=parents, weight=weight, label=label))
        return cls(nodes)

    # ---- basic accessors ------------------------------------------------ #

    def __len__(self) -> int:
        return len(self._nodes)

    def __contains__(self, node_id: object) -> bool:
        return node_id in self._nodes

    def node(self, node_id: str) -> DagNode:
        return self._nodes[node_id]

    def ids(self) -> tuple[str, ...]:
        return tuple(self._nodes)

    # ---- topology ------------------------------------------------------- #

    def _compute_topo(self) -> tuple[str, ...]:
        indegree = {nid: len(node.parents) for nid, node in self._nodes.items()}
        # Deterministic: process ready nodes in sorted id order.
        ready = sorted(nid for nid, d in indegree.items() if d == 0)
        order: list[str] = []
        while ready:
            nid = ready.pop(0)
            order.append(nid)
            newly_ready = []
            for child in self._children[nid]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    newly_ready.append(child)
            if newly_ready:
                ready = sorted(ready + newly_ready)
        if len(order) != len(self._nodes):
            raise DagError("cycle detected: graph is not a DAG")
        return tuple(order)

    def topological_order(self) -> tuple[str, ...]:
        return self._topo

    # ---- frontier ------------------------------------------------------- #

    def ready_nodes(self, done: Iterable[str] = ()) -> tuple[str, ...]:
        """Nodes not yet done whose parents are all done (dispatchable now)."""
        done_set = set(done)
        out = [
            nid
            for nid in self._topo
            if nid not in done_set
            and all(p in done_set for p in self._nodes[nid].parents)
        ]
        return tuple(out)

    def blocked_nodes(self, done: Iterable[str] = ()) -> tuple[str, ...]:
        """Nodes not yet done that still have at least one unmet parent."""
        done_set = set(done)
        out = [
            nid
            for nid in self._topo
            if nid not in done_set
            and any(p not in done_set for p in self._nodes[nid].parents)
        ]
        return tuple(out)

    # ---- reachability --------------------------------------------------- #

    def ancestors(self, node_id: str) -> frozenset[str]:
        if node_id not in self._nodes:
            raise DagError(f"unknown node {node_id!r}")
        seen: set[str] = set()
        stack = list(self._nodes[node_id].parents)
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(self._nodes[cur].parents)
        return frozenset(seen)

    def descendants(self, node_id: str) -> frozenset[str]:
        if node_id not in self._nodes:
            raise DagError(f"unknown node {node_id!r}")
        seen: set[str] = set()
        stack = list(self._children[node_id])
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(self._children[cur])
        return frozenset(seen)

    # ---- critical path -------------------------------------------------- #

    def critical_path(self) -> CriticalPath:
        """Longest weighted path through the DAG (the schedule lower bound)."""
        if not self._nodes:
            return CriticalPath((), 0.0)
        best_weight: dict[str, float] = {}
        best_prev: dict[str, str | None] = {}
        for nid in self._topo:  # parents precede children
            node = self._nodes[nid]
            if not node.parents:
                best_weight[nid] = node.weight
                best_prev[nid] = None
                continue
            chosen_parent = max(node.parents, key=lambda p: best_weight[p])
            best_weight[nid] = best_weight[chosen_parent] + node.weight
            best_prev[nid] = chosen_parent
        end = max(best_weight, key=lambda n: best_weight[n])
        chain: list[str] = []
        cur: str | None = end
        while cur is not None:
            chain.append(cur)
            cur = best_prev[cur]
        chain.reverse()
        return CriticalPath(tuple(chain), best_weight[end])


__all__ = ["DagError", "DagNode", "CriticalPath", "MissionDag"]
