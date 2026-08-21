import builtins
import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest


def load_plugin():
    root = Path(__file__).resolve().parents[2]
    init = root / "plugins" / "dz23-guardrail" / "__init__.py"
    spec = importlib.util.spec_from_file_location("dz23_guardrail_under_test", init)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_guardrail_loads_through_real_plugin_manager(tmp_path, monkeypatch) -> None:
    """The shipped guardrail must load without a user opt-in."""
    from hermes_cli import plugins as plugins_module
    from hermes_cli.plugins import PluginManager

    root = Path(__file__).resolve().parents[2]
    bundled = tmp_path / "bundled"
    shutil.copytree(root / "plugins" / "dz23-guardrail", bundled / "dz23-guardrail")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(plugins_module, "get_bundled_plugins_dir", lambda: bundled)

    manager = PluginManager()
    monkeypatch.setattr(manager, "_scan_entry_points", lambda: [])
    manager.discover_and_load()

    loaded = manager._plugins["dz23-guardrail"]
    assert loaded.enabled is True
    assert set(loaded.hooks_registered) == {
        "on_session_start",
        "pre_tool_call",
        "post_tool_call",
        "pre_verify",
        "post_api_request",
        "subagent_stop",
        "on_session_end",
    }


def test_security_critical_plugin_load_failure_aborts_startup(tmp_path, monkeypatch) -> None:
    """A broken security boundary cannot degrade to a warning."""
    from hermes_cli import plugins as plugins_module
    from hermes_cli.plugins import PluginManager

    bundled = tmp_path / "bundled"
    plugin_dir = bundled / "critical"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.yaml").write_text(
        "name: critical\nkind: backend\nsecurity_critical: true\n",
        encoding="utf-8",
    )
    (plugin_dir / "__init__.py").write_text(
        "def register(ctx):\n    raise RuntimeError('critical boom')\n",
        encoding="utf-8",
    )
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(plugins_module, "get_bundled_plugins_dir", lambda: bundled)

    manager = PluginManager()
    monkeypatch.setattr(manager, "_scan_entry_points", lambda: [])

    with pytest.raises(RuntimeError, match="security-critical plugin.*critical.*critical boom"):
        manager.discover_and_load()


@pytest.mark.parametrize(
    ("security_critical", "blocked"),
    [(True, True), (False, False)],
)
def test_pre_tool_hook_failure_is_fail_closed_only_for_security_plugins(
    tmp_path, monkeypatch, security_critical: bool, blocked: bool
) -> None:
    from hermes_cli import plugins as plugins_module
    from hermes_cli.plugins import PluginManager

    bundled = tmp_path / "bundled"
    plugin_dir = bundled / "hook-failure"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.yaml").write_text(
        "\n".join(
            [
                "name: hook-failure",
                "kind: backend",
                f"security_critical: {str(security_critical).lower()}",
            ]
        ),
        encoding="utf-8",
    )
    (plugin_dir / "__init__.py").write_text(
        "def register(ctx):\n"
        "    def broken(**kwargs):\n"
        "        raise RuntimeError('hook boom')\n"
        "    ctx.register_hook('pre_tool_call', broken)\n",
        encoding="utf-8",
    )
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(plugins_module, "get_bundled_plugins_dir", lambda: bundled)

    manager = PluginManager()
    monkeypatch.setattr(manager, "_scan_entry_points", lambda: [])
    manager.discover_and_load()

    results = manager.invoke_hook("pre_tool_call", tool_name="terminal", args={"command": "echo ok"})
    assert bool(results) is blocked
    if blocked:
        assert results[0]["action"] == "block"
        assert "security-critical" in results[0]["message"]


def test_destructive_commands_are_blocked_by_hook() -> None:
    plugin = load_plugin()

    for command in ("rm -rf /tmp/teste", "DROP TABLE users", "docker system prune -af"):
        result = plugin.on_pre_tool_call("terminal", {"command": command})
        assert result["action"] == "block"
        assert "DZ23 Guardrail" in result["message"]


def test_guardrail_uses_raw_conservative_variant_when_core_parser_import_fails(monkeypatch) -> None:
    plugin = load_plugin()
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "tools.approval":
            raise ImportError("approval parser unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    result = plugin.on_pre_tool_call("terminal", {"command": "rm -rf /tmp/teste"})

    assert result["action"] == "block"
    assert "recursive forced rm" in result["message"]


@pytest.mark.parametrize(
    "command",
    [
        r"del /s /q C:\Users\zodyp\Documents",
        r"rd /s /q C:\projeto",
        r"Remove-Item -Recurse -Force C:\Users\zodyp",
        "rm -r -f /tmp/x",
        "find . -delete",
        "git clean -fdx",
        "DROP DATABASE prod",
        "TRUNCATE TABLE users",
        "docker volume prune -f",
        "rm -rf /tmp/x",
    ],
)
def test_destructive_denylist_covers_windows(command: str) -> None:
    plugin = load_plugin()

    result = plugin.on_pre_tool_call("terminal", {"command": command})

    assert result is not None
    assert result["action"] == "block"


@pytest.mark.parametrize(
    "command",
    [
        "git clean -n",
        "printf 'rm -rf is dangerous'",
        "cat docs/destructive-commands.md",
        "SELECT 'DROP TABLE is documented'",
    ],
)
def test_destructive_denylist_avoids_documentation_false_positives(command: str) -> None:
    plugin = load_plugin()

    assert plugin.on_pre_tool_call("terminal", {"command": command}) is None


def test_guardrail_does_not_block_file_content(tmp_path, monkeypatch) -> None:
    plugin = load_plugin()
    monkeypatch.setenv("HERMES_GUARDRAIL_WORKSPACE_ROOTS", str(tmp_path))

    assert (
        plugin.on_pre_tool_call(
            "write_file",
            {
                "path": str(tmp_path / "safety.md"),
                "content": "Never run rm -rf / or DROP TABLE users.",
            },
        )
        is None
    )


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


def test_workspace_gate_resolves_relative_and_symlink(tmp_path, monkeypatch) -> None:
    plugin = load_plugin()
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    monkeypatch.setenv("HERMES_GUARDRAIL_WORKSPACE_ROOTS", str(workspace))
    monkeypatch.setenv("TERMINAL_CWD", str(workspace))

    traversal = plugin.on_pre_tool_call("write_file", {"path": "../outside/file.txt"})
    assert traversal is not None
    assert traversal["action"] == "approve"

    link = workspace / "linked-outside"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            raise
        # A junction exercises the same Windows reparse-point escape without
        # requiring Developer Mode or SeCreateSymbolicLinkPrivilege.
        subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(outside)],
            check=True,
            capture_output=True,
            text=True,
        )
    linked = plugin.on_pre_tool_call("write_file", {"path": str(link / "file.txt")})
    assert linked is not None
    assert linked["action"] == "approve"


def test_workspace_gate_ignores_process_cwd(tmp_path, monkeypatch) -> None:
    plugin = load_plugin()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("TERMINAL_CWD", str(workspace))
    monkeypatch.delenv("HERMES_GUARDRAIL_WORKSPACE_ROOTS", raising=False)
    monkeypatch.chdir(tmp_path)

    result = plugin.on_pre_tool_call("write_file", {"path": str(tmp_path / "outside.txt")})

    assert result is not None
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


@pytest.mark.parametrize(
    ("command", "result", "status", "verified"),
    [
        ("npm test", {"exit_code": 1, "stdout": "all output looked fine"}, "success", False),
        ("echo npm test", {"exit_code": 0}, "success", False),
        ("pytest", {"exit_code": 0}, "success", True),
        ("tox", {"exit_code": 0}, "success", True),
        ("nox", {"exit_code": 0}, "success", True),
        ("npm test", "npm test", "success", False),
    ],
)
def test_verification_requires_real_exit_code(
    command: str, result, status: str, verified: bool
) -> None:
    plugin = load_plugin()
    session = f"verify-{command}-{verified}"
    plugin.on_post_tool_call(
        "write_file", {"path": "src/app.ts"}, {"ok": True}, "success", session
    )

    plugin.on_post_tool_call(
        "terminal", {"command": command}, result, status, session
    )

    decision = plugin.on_pre_verify(
        session_id=session, coding=True, changed_paths=["src/app.ts"]
    )
    assert (decision is None) is verified


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
