from __future__ import annotations

import json


def test_capture_mode_records_decisions_without_calling_human_gate(
    tmp_path, monkeypatch
) -> None:
    from agent.replay_capture import capture_authorization, reset_capture_state
    from hermes_cli.plugins import _PreToolCallDirective

    destination = tmp_path / "capture.jsonl"
    monkeypatch.setenv("HERMES_REPLAY_DECISION_CAPTURE", str(destination))
    monkeypatch.setenv("HERMES_REPLAY_APPROVALS_JSON", '["approved"]')
    reset_capture_state()

    block = capture_authorization(
        _PreToolCallDirective(action="approve", rule_key="outside:file"),
        "write_file",
    )

    assert block is not None and "REPLAY_CAPTURE" in block
    event = json.loads(destination.read_text(encoding="utf-8"))
    assert event == {
        "approval": "approved",
        "approval_path": "outside:file",
        "tool": "write_file",
    }


def test_capture_mode_is_inert_without_explicit_environment(monkeypatch) -> None:
    from agent.replay_capture import capture_authorization, reset_capture_state
    from hermes_cli.plugins import _PreToolCallDirective

    monkeypatch.delenv("HERMES_REPLAY_DECISION_CAPTURE", raising=False)
    reset_capture_state()

    assert capture_authorization(_PreToolCallDirective(), "terminal") is None
