"""Tests for the code graph + impact analysis + test selection (Wave 4)."""

from __future__ import annotations

from agent.code_graph import CodeGraph, Symbol
from agent.impact_selection import select_impacted_tests


def _graph() -> CodeGraph:
    g = CodeGraph()
    # db <- service <- route ; test_route depends on route ; test_util depends on util
    for sid, file, kind in [
        ("db.py::User", "db.py", "db"),
        ("svc.py::get_user", "svc.py", "service"),
        ("routes.py::login", "routes.py", "route"),
        ("util.py::fmt", "util.py", "function"),
        ("tests/test_login.py::t", "tests/test_login.py", "test"),
        ("tests/test_util.py::t", "tests/test_util.py", "test"),
    ]:
        g.add_symbol(Symbol(sid, file, kind))
    g.add_edge("svc.py::get_user", "db.py::User")        # service depends on db
    g.add_edge("routes.py::login", "svc.py::get_user")   # route depends on service
    g.add_edge("tests/test_login.py::t", "routes.py::login")
    g.add_edge("tests/test_util.py::t", "util.py::fmt")
    return g


def test_dependents_and_dependencies_transitive():
    g = _graph()
    # who depends (transitively) on the db symbol -> service, route, test_login
    deps = g.dependents("db.py::User")
    assert deps == {"svc.py::get_user", "routes.py::login", "tests/test_login.py::t"}
    # what does the route depend on -> service + db
    assert g.dependencies("routes.py::login") == {"svc.py::get_user", "db.py::User"}


def test_blast_radius_and_impacted_tests():
    g = _graph()
    radius = g.blast_radius(["db.py::User"])
    assert "routes.py::login" in radius and "db.py::User" in radius
    # only the login test is impacted by a db change; util test is not
    assert g.impacted_tests(["db.py::User"]) == {"tests/test_login.py::t"}
    assert g.impacted_tests(["util.py::fmt"]) == {"tests/test_util.py::t"}


def test_cycle_is_handled():
    g = CodeGraph()
    g.add_symbol(Symbol("a", "a.py"))
    g.add_symbol(Symbol("b", "b.py"))
    g.add_edge("a", "b")
    g.add_edge("b", "a")   # cycle
    assert g.dependents("a") == {"b", "a"}   # terminates, no infinite loop


def test_incremental_remove_file():
    g = _graph()
    g.remove_file("util.py")
    assert "util.py::fmt" not in g
    # the util test no longer resolves an impact through util
    assert g.impacted_tests(["util.py::fmt"]) == frozenset()


def test_select_impacted_tests_by_graph():
    g = _graph()
    res = select_impacted_tests(
        g, changed_files=["db.py"],
        all_test_files=["tests/test_login.py", "tests/test_util.py"],
    )
    assert res.fail_open is False
    assert res.tests == {"tests/test_login.py"}


def test_select_fails_open_on_uncovered_change():
    g = _graph()
    res = select_impacted_tests(
        g, changed_files=["brand_new_file.py"],   # not in graph
        all_test_files=["tests/test_login.py", "tests/test_util.py"],
    )
    assert res.fail_open is True
    assert res.tests == {"tests/test_login.py", "tests/test_util.py"}   # run everything


def test_no_changes_selects_nothing():
    g = _graph()
    res = select_impacted_tests(g, changed_files=[], all_test_files=["tests/test_login.py"])
    assert res.tests == frozenset() and res.reason == "no_changes"
