"""Tests for mission trace + structured redacted logging (§58/§59)."""

from __future__ import annotations

import json

from agent.mission_trace import MissionTrace, TraceEvent, format_log


def test_timeline_is_ordered_and_correlated():
    tr = MissionTrace()
    tr.append(TraceEvent("m1", "node_start", at=2.0, node_id="a", run_id="r1"))
    tr.append(TraceEvent("m1", "result", at=3.0, node_id="a", run_id="r1", status="ok"))
    tr.append(TraceEvent("m2", "node_start", at=1.0, node_id="x", run_id="r2"))
    tl = tr.timeline("m1")
    assert [e.kind for e in tl] == ["node_start", "result"]   # ordered by time
    assert all(e.mission_id == "m1" for e in tl)
    assert [e.node_id for e in tr.by_run("r1")] == ["a", "a"]  # correlation by run_id


def test_trace_event_to_dict_drops_none():
    d = TraceEvent("m1", "tool_call", at=1.0, tool_call_id="tc1").to_dict()
    assert d["tool_call_id"] == "tc1"
    assert "model" not in d      # None fields omitted


def test_structured_log_has_fields_and_is_json():
    line = format_log({
        "timestamp": 1.0, "severity": "INFO", "component": "gateway",
        "mission_id": "m1", "node_id": "a", "run_id": "r1",
        "event": "node_done", "message": "ok", "duration_ms": 12,
    })
    obj = json.loads(line)
    assert obj["mission_id"] == "m1" and obj["event"] == "node_done"
    # canonical field ordering: timestamp first
    assert list(obj.keys())[0] == "timestamp"


def test_log_redacts_sensitive_key_and_value():
    line = format_log({
        "severity": "ERROR", "component": "auth",
        "authorization": "Bearer sk-secret", "message": "login token=ghp_abcdefghijklmnopqrstuvwxyz0123456789",
    })
    # sensitive-named key masked
    obj = json.loads(line)
    assert obj["authorization"] == "[REDACTED]"
    # value-pattern redaction scrubbed the github token in the message
    assert "ghp_abcdefghijklmnopqrstuvwxyz0123456789" not in line
