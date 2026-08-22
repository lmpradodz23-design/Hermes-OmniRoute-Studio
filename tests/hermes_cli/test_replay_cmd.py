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


def test_replay_against_model_uses_decision_only_probe_and_prints_diff(
    tmp_path, capsys, monkeypatch
) -> None:
    from hermes_cli import replay_cmd

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

    monkeypatch.setattr(
        replay_cmd,
        "_run_model_probe",
        lambda _replay, _model: (["write_file"], ["blocked"], "probe-model"),
    )

    assert replay_cmd.cmd_replay(args) == 0
    output = capsys.readouterr().out
    assert "Model decision diff" in output
    assert "terminal -> write_file" in output
    assert "automatic -> blocked" in output


def test_model_probe_launches_bounded_capture_process(tmp_path, monkeypatch) -> None:
    from agent.session_recording import SessionReplay
    from hermes_cli import replay_cmd

    replay = SessionReplay(
        [
            {"t": "turn_start", "user_message": "build a safe app"},
            {
                "t": "tool_call",
                "tool": "terminal",
                "approval": {"verdict": "approved"},
            },
        ],
        tmp_path / "source.jsonl",
    )
    observed = {}

    def _run(command, **kwargs):
        observed["command"] = command
        observed["env"] = kwargs["env"]
        capture = kwargs["env"]["HERMES_REPLAY_DECISION_CAPTURE"]
        with open(capture, "w", encoding="utf-8") as stream:
            stream.write(
                json.dumps({
                    "tool": "terminal",
                    "approval": "approved",
                    "approval_path": "runtime",
                })
                + "\n"
            )
        return type("Completed", (), {"returncode": 0, "stderr": ""})()

    monkeypatch.setattr(replay_cmd.subprocess, "run", _run)

    tools, approvals, route = replay_cmd._run_model_probe(replay, "provider/model")

    assert tools == ["terminal"]
    assert approvals == ["approved"]
    assert route == "provider/model"
    assert "--max-turns" in observed["command"]
    assert "--run-budget" in observed["command"]
    assert observed["env"]["HERMES_REPLAY_APPROVALS_JSON"] == '["approved"]'
