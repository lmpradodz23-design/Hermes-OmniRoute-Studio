import importlib.util
from pathlib import Path


def load_plugin():
    root = Path(__file__).resolve().parents[2]
    init = root / "plugins" / "dz23-guardrail" / "__init__.py"
    spec = importlib.util.spec_from_file_location("dz23_guardrail_under_test", init)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_destructive_commands_are_blocked_by_hook() -> None:
    plugin = load_plugin()

    for command in ("rm -rf /tmp/teste", "DROP TABLE users", "docker system prune -af"):
        result = plugin.on_pre_tool_call("terminal", {"command": command})
        assert result["action"] == "block"
        assert "DZ23 Guardrail" in result["message"]


def test_outside_workspace_write_requires_approval(tmp_path, monkeypatch) -> None:
    plugin = load_plugin()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("HERMES_GUARDRAIL_WORKSPACE_ROOTS", str(workspace))

    assert (
        plugin.on_pre_tool_call("write_file", {"path": str(workspace / "ok.txt")})
        is None
    )
    result = plugin.on_pre_tool_call(
        "write_file", {"path": str(tmp_path / "outside.txt")}
    )
    assert result["action"] == "approve"


def test_code_cannot_finish_without_fresh_verification() -> None:
    plugin = load_plugin()
    session = "session-a"

    plugin.on_post_tool_call(
        "write_file", {"path": "src/app.ts"}, {"ok": True}, "success", session
    )
    assert (
        plugin.on_pre_verify(
            session_id=session, coding=True, changed_paths=["src/app.ts"]
        )["action"]
        == "continue"
    )

    plugin.on_post_tool_call(
        "terminal", {"command": "npm test"}, {"exit_code": 0}, "success", session
    )
    assert (
        plugin.on_pre_verify(
            session_id=session, coding=True, changed_paths=["src/app.ts"]
        )
        is None
    )


def test_failed_check_does_not_satisfy_verification_gate() -> None:
    plugin = load_plugin()
    session = "session-b"

    plugin.on_post_tool_call(
        "terminal",
        {"command": "npm run typecheck"},
        {"exit_code": 1},
        "failed",
        session,
    )
    assert (
        plugin.on_pre_verify(
            session_id=session, coding=True, changed_paths=["src/app.ts"]
        )["action"]
        == "continue"
    )


def test_task_report_tracks_evidence_without_logging_tool_payloads(
    tmp_path, monkeypatch
) -> None:
    plugin = load_plugin()
    workspace = tmp_path / "workspace"
    reports = tmp_path / "reports"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    monkeypatch.setattr(plugin, "_report_root", lambda: reports)
    session = "report-session"

    plugin.on_session_start(session_id=session)
    plugin.on_post_tool_call(
        "write_file",
        {"path": "src/app.ts", "content": "PASSWORD=do-not-log-this"},
        {"ok": True},
        "success",
        session,
    )
    plugin.on_pre_verify(session_id=session, coding=True, changed_paths=["src/app.ts"])
    plugin.on_post_api_request(
        session_id=session,
        provider="omniroute",
        model="auto/coding",
        usage={"input_tokens": 120, "output_tokens": 30},
    )
    plugin.on_subagent_stop(
        parent_session_id=session,
        child_role="Testing Agent",
        child_status="completed",
        duration_ms=250,
    )
    plugin.on_session_end(session_id=session, completed=True)

    report_files = list(reports.glob("report-*.md"))
    assert len(report_files) == 1
    report = report_files[0].read_text(encoding="utf-8")
    assert "src/app.ts" in report
    assert "`write_file`" in report
    assert "omniroute/auto/coding: input=120, output=30 tokens" in report
    assert "Testing Agent: completed (250 ms)" in report
    assert "Auto-commit/push: disabled" in report
    assert "do-not-log-this" not in report


def test_task_report_failure_never_breaks_session_teardown(monkeypatch) -> None:
    plugin = load_plugin()
    session = "report-failure"
    plugin.on_session_start(session_id=session)
    plugin.on_post_tool_call(
        "write_file", {"path": "app.py"}, {"ok": True}, "success", session
    )
    monkeypatch.setattr(
        plugin,
        "_write_task_report",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError()),
    )

    plugin.on_session_end(session_id=session, completed=True)
