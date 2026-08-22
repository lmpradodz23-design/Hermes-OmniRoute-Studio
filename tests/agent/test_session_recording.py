from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone


def test_recorder_is_opt_in_and_never_creates_a_file_when_disabled(tmp_path) -> None:
    from agent.session_recording import RecordingConfig, SessionRecorder

    recorder = SessionRecorder(
        RecordingConfig(enabled=False), tmp_path, redactor=lambda value: value
    )

    assert recorder.append("session-a", "turn_start", {"turn": 1}) is False
    assert list(tmp_path.rglob("*.jsonl")) == []


def test_recorder_hashes_raw_values_and_persists_only_redacted_payload(
    tmp_path,
) -> None:
    from agent.session_recording import RecordingConfig, SessionRecorder, sha256_json

    recorder = SessionRecorder(
        RecordingConfig(enabled=True),
        tmp_path,
        redactor=lambda value: {
            **value,
            "args": {"token": "[REDACTED]", "command": value["args"]["command"]},
        },
    )
    raw_args = {"token": "super-secret", "command": "pytest -q"}

    assert recorder.append(
        "session-a",
        "tool_call",
        {"turn": 4, "tool": "terminal", "args": raw_args},
        hash_fields=("args",),
    )
    event = json.loads((tmp_path / "session-a.jsonl").read_text(encoding="utf-8"))

    assert event["t"] == "tool_call"
    assert event["args"] == {"token": "[REDACTED]", "command": "pytest -q"}
    assert event["args_sha256"] == sha256_json(raw_args)
    assert "super-secret" not in json.dumps(event)


def test_recorder_fails_closed_when_redaction_is_unavailable(tmp_path) -> None:
    from agent.session_recording import RecordingConfig, SessionRecorder

    def broken(_value):
        raise RuntimeError("redactor unavailable")

    recorder = SessionRecorder(RecordingConfig(enabled=True), tmp_path, redactor=broken)

    assert recorder.append("session-a", "tool_call", {"args": {"token": "x"}}) is False
    assert list(tmp_path.rglob("*.jsonl")) == []


def test_retention_removes_only_expired_recordings(tmp_path) -> None:
    from agent.session_recording import RecordingConfig, SessionRecorder

    now = datetime(2026, 8, 21, tzinfo=timezone.utc)
    recorder = SessionRecorder(
        RecordingConfig(enabled=True, retention_days=7),
        tmp_path,
        redactor=lambda value: value,
        clock=lambda: now,
    )
    old = tmp_path / "old.jsonl"
    recent = tmp_path / "recent.jsonl"
    old.write_text("{}\n", encoding="utf-8")
    recent.write_text("{}\n", encoding="utf-8")
    old_time = (now - timedelta(days=8)).timestamp()
    recent_time = (now - timedelta(days=2)).timestamp()
    import os

    os.utime(old, (old_time, old_time))
    os.utime(recent, (recent_time, recent_time))

    assert recorder.prune() == 1
    assert old.exists() is False
    assert recent.exists() is True


def test_replay_assertions_detect_tool_and_approval_drift(tmp_path) -> None:
    from agent.session_recording import ReplayAssertionError, SessionReplay

    path = tmp_path / "session-a.jsonl"
    rows = [
        {"t": "tool_call", "tool": "terminal", "approval": {"verdict": "approved"}},
        {"t": "tool_result", "tool": "terminal", "exit_code": 0},
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    replay = SessionReplay.load(path)

    replay.assert_decisions(tools=["terminal"], approvals=["approved"])
    try:
        replay.assert_decisions(tools=["write_file"], approvals=["denied"])
    except ReplayAssertionError as exc:
        assert "tool sequence" in str(exc)
        assert "approval" in str(exc)
    else:
        raise AssertionError("decision drift was not detected")


def test_emit_test_generates_an_executable_regression_fixture(tmp_path) -> None:
    from agent.session_recording import SessionReplay

    path = tmp_path / "session-a.jsonl"
    path.write_text(
        json.dumps({
            "t": "tool_call",
            "tool": "terminal",
            "approval": {"verdict": "approved"},
        })
        + "\n",
        encoding="utf-8",
    )

    emitted = SessionReplay.load(path).emit_pytest("session-a")

    compile(emitted, "generated_replay_test.py", "exec")
    assert "EXPECTED_TOOLS = ['terminal']" in emitted
    assert "EXPECTED_APPROVALS = ['approved']" in emitted
    namespace = {}
    exec(emitted, namespace)
    namespace["test_replay_session_a"]()
