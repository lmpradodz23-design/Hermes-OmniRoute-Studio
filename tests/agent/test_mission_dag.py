"""Tests for the pure Mission DAG reader (agent/mission_dag.py)."""

from __future__ import annotations

import pytest

from agent.mission_dag import DagError, DagNode, MissionDag


def _diamond() -> MissionDag:
    # a -> b, a -> c, (b,c) -> d
    return MissionDag(
        [
            DagNode("a", weight=2.0),
            DagNode("b", parents=("a",), weight=3.0),
            DagNode("c", parents=("a",), weight=10.0),
            DagNode("d", parents=("b", "c"), weight=1.0),
        ]
    )


def test_topological_order_is_valid_and_deterministic():
    dag = _diamond()
    order = dag.topological_order()
    assert order[0] == "a"
    assert order[-1] == "d"
    pos = {n: i for i, n in enumerate(order)}
    for nid in dag.ids():
        for parent in dag.node(nid).parents:
            assert pos[parent] < pos[nid]
    # deterministic: b before c (sorted id order among ready)
    assert pos["b"] < pos["c"]


def test_ready_and_blocked_frontier():
    dag = _diamond()
    assert dag.ready_nodes(done=()) == ("a",)
    assert dag.ready_nodes(done={"a"}) == ("b", "c")
    assert dag.blocked_nodes(done={"a"}) == ("d",)
    assert dag.ready_nodes(done={"a", "b", "c"}) == ("d",)
    assert dag.ready_nodes(done={"a", "b", "c", "d"}) == ()
    assert dag.blocked_nodes(done={"a", "b", "c", "d"}) == ()


def test_unknown_parent_rejected():
    with pytest.raises(DagError):
        MissionDag([DagNode("x", parents=("ghost",))])


def test_duplicate_id_rejected():
    with pytest.raises(DagError):
        MissionDag([DagNode("a"), DagNode("a")])


def test_cycle_detected():
    # a -> b -> a is not expressible via parents without both referencing each
    # other; build it explicitly.
    with pytest.raises(DagError):
        MissionDag([DagNode("a", parents=("b",)), DagNode("b", parents=("a",))])


def test_critical_path_is_longest_weighted_path():
    dag = _diamond()
    cp = dag.critical_path()
    # a(2) -> c(10) -> d(1) = 13 beats a(2)->b(3)->d(1)=6
    assert cp.nodes == ("a", "c", "d")
    assert cp.weight == pytest.approx(13.0)


def test_ancestors_and_descendants():
    dag = _diamond()
    assert dag.ancestors("d") == frozenset({"a", "b", "c"})
    assert dag.descendants("a") == frozenset({"b", "c", "d"})
    assert dag.ancestors("a") == frozenset()
    assert dag.descendants("d") == frozenset()


def test_from_mapping_and_empty():
    dag = MissionDag.from_mapping(
        {
            "root": {"weight": 1},
            "leaf": {"parents": ["root"], "weight": 5, "label": "final"},
        }
    )
    assert dag.node("leaf").label == "final"
    assert dag.critical_path().nodes == ("root", "leaf")
    empty = MissionDag([])
    assert len(empty) == 0
    assert empty.critical_path().weight == 0.0
    assert empty.ready_nodes() == ()
