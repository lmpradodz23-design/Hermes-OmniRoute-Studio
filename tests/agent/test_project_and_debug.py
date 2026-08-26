"""Tests for ProjectModel (§40) and DebugSession (§45)."""

from __future__ import annotations

import pytest

from agent.debug_session import DebugError, DebugSession, DebugState
from agent.project_model import detect


# ---- project model ------------------------------------------------------ #


def test_detect_languages_frameworks_entrypoints():
    files = [
        "app.py", "svc/models.py", "web/index.tsx", "web/app.tsx",
        "migrations/0001_init.py", ".github/workflows/ci.yml", "tests/test_x.py",
    ]
    deps = ["django==5", "psycopg2", "stripe", "react"]
    m = detect(files, deps)
    assert m.primary_language == "python"
    assert m.languages["typescript"] == 2
    assert "django" in m.frameworks and "react" in m.frameworks
    assert "app.py" in m.entrypoints
    assert m.migrations == ("migrations/0001_init.py",)
    assert m.has_ci is True
    assert "postgres" in m.db_engines
    assert "stripe" in m.integrations
    assert "tests" in m.test_dirs


def test_detect_empty():
    m = detect([], [])
    assert m.primary_language is None and m.frameworks == frozenset()


# ---- debug session ------------------------------------------------------ #


def test_no_fix_without_root_cause():
    s = DebugSession("crash on login")
    s.reproduce(True)
    s.observe("stacktrace at auth.py:42")
    with pytest.raises(DebugError):
        s.apply_patch("patch:1")          # Iron Law: no root cause yet


def test_full_debug_flow_resolves():
    s = DebugSession("500 on /login")
    s.reproduce(True)
    s.observe("null user")
    h = s.hypothesize("session not loaded")
    s.test_hypothesis(h, supported=True)
    s.set_root_cause("missing await on load_user", evidence_ref="log:1")
    s.apply_patch("patch:await")
    assert s.verify(ok=True) is DebugState.RESOLVED


def test_root_cause_requires_supported_hypothesis():
    s = DebugSession("x")
    s.reproduce(True)
    s.observe("o")
    s.hypothesize("guess")   # not tested/supported
    with pytest.raises(DebugError):
        s.set_root_cause("rc", "e")


def test_failed_verify_reopens_and_invalidates_root_cause():
    s = DebugSession("x")
    s.reproduce(True)
    s.observe("o")
    h = s.hypothesize("h")
    s.test_hypothesis(h, True)
    s.set_root_cause("rc", "e")
    s.apply_patch("p")
    assert s.verify(ok=False) is DebugState.HYPOTHESIZING
    assert s.root_cause is None          # patch didn't fix -> root cause invalidated


def test_cannot_proceed_without_reproduction():
    s = DebugSession("flaky")
    with pytest.raises(DebugError):
        s.reproduce(False)
    assert s.state is DebugState.FAILED
