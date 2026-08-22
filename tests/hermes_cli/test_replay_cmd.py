from __future__ import annotations

import argparse
import json


def _recording(path) -> None:
    rows = [
        {"t": "turn_start", "turn_id": "turn-1"},
        {
            "t": "tool_call",
            "tool": "terminal",
            "approval": {"verdict": "automatic"},
        },
        {"t": "tool_result", "tool": "terminal", "exit_code": 0},
        {"t": "turn_end", "outcome": "completed"},
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_replay_command_validates_recorded_tool_and_approval_evidence(
    tmp_path, capsys
) -> None:
    from hermes_cli.replay_cmd import cmd_replay

    root = tmp_path / "session-recordings"
    root.mkdir()
    _recording(root / "session-a.jsonl")
    args = argparse.Namespace(
        session_id="session-a",
        against_model=None,
        assert_tools=True,
        assert_approvals=True,
        emit_test=None,
        recordings_dir=str(root),
    )

    assert cmd_replay(args) == 0
    output = capsys.readouterr().out
    assert "1 tool call" in output
    assert "approval evidence: valid" in output


def test_replay_emit_test_writes_a_runnable_fixture(tmp_path) -> None:
    from hermes_cli.replay_cmd import cmd_replay

    root = tmp_path / "session-recordings"
    root.mkdir()
    _recording(root / "session-a.jsonl")
    destination = tmp_path / "test_recorded_session.py"
    args = argparse.Namespace(
        session_id="session-a",
        against_model=None,
        assert_tools=False,
        assert_approvals=False,
        emit_test=str(destination),
        recordings_dir=str(root),
    )

    assert cmd_replay(args) == 0
    emitted = destination.read_text(encoding="utf-8")
    compile(emitted, str(destination), "exec")
    assert "EXPECTED_TOOLS = ['terminal']" in emitted


def test_replay_emit_test_without_path_prints_fixture_for_shell_redirection(
    tmp_path, capsys
) -> None:
    from hermes_cli.replay_cmd import cmd_replay

    root = tmp_path / "session-recordings"
    root.mkdir()
    _recording(root / "session-a.jsonl")
    args = argparse.Namespace(
        session_id="session-a",
        against_model=None,
        assert_tools=False,
        assert_approvals=False,
        emit_test="-",
        recordings_dir=str(root),
    )

    assert cmd_replay(args) == 0
    output = capsys.readouterr().out
    assert "EXPECTED_TOOLS = ['terminal']" in output
    assert "Replay valid" not in output


def test_replay_rejects_missing_approval_evidence(tmp_path, capsys) -> None:
    from hermes_cli.replay_cmd import cmd_replay

    root = tmp_path / "session-recordings"
    root.mkdir()
    (root / "session-a.jsonl").write_text(
        json.dumps({"t": "tool_call", "tool": "terminal"}) + "\n",
        encoding="utf-8",
    )
    args = argparse.Namespace(
        session_id="session-a",
        against_model=None,
        assert_tools=False,
        assert_approvals=True,
        emit_test=None,
        recordings_dir=str(root),
    )

    assert cmd_replay(args) == 2
    assert "missing approval verdict" in capsys.readouterr().err


def test_replay_detects_current_guardrail_verdict_drift(
    tmp_path, capsys, monkeypatch
) -> None:
    from hermes_cli import replay_cmd

    root = tmp_path / "session-recordings"
    root.mkdir()
    _recording(root / "session-a.jsonl")
    monkeypatch.setattr(
        replay_cmd, "_runtime_approval_verdicts", lambda _replay: ["blocked"]
    )
    args = argparse.Namespace(
        session_id="session-a",
        against_model=None,
        assert_tools=False,
        assert_approvals=True,
        emit_test=None,
        recordings_dir=str(root),
    )

    assert replay_cmd.cmd_replay(args) == 2
    error = capsys.readouterr().err
    assert "approval verdict drift" in error
    assert "recorded=['automatic']" in error
    assert "current=['blocked']" in error


def test_replay_refuses_model_execution_until_a_safe_runner_is_available(
    tmp_path, capsys
) -> None:
    from hermes_cli.replay_cmd import cmd_replay

    root = tmp_path / "session-recordings"
    root.mkdir()
    _recording(root / "session-a.jsonl")
    args = argparse.Namespace(
        session_id="session-a",
        against_model="provider/model",
        assert_tools=False,
        assert_approvals=False,
        emit_test=None,
        recordings_dir=str(root),
    )

    assert cmd_replay(args) == 2
    assert "does not execute recorded tools" in capsys.readouterr().err
