"""Mission observability: correlated trace + structured JSON logs (§58/§59).

Gives every mission a single correlated timeline (mission_id -> node_id -> run_id
-> agent -> model -> tool -> result -> retry -> evidence) and a structured JSON
log line with mandatory secret redaction. Reuses the repo's real redaction
(agent.redact.redact_sensitive_text) so log output cannot leak tokens/secrets.

Pure/in-memory core (persist via the existing MissionStore events); no secrets
stored in the trace itself.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from agent.redact import redact_sensitive_text


@dataclass(frozen=True)
class TraceEvent:
    mission_id: str
    kind: str                      # e.g. node_start / model_call / tool_call / result / retry / evidence
    at: float
    node_id: str | None = None
    run_id: str | None = None      # correlation id across sinks
    agent_id: str | None = None
    model: str | None = None
    provider: str | None = None
    tool_call_id: str | None = None
    duration_ms: float | None = None
    status: str | None = None
    failure_type: str | None = None
    evidence_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


class MissionTrace:
    """An ordered, correlated event log for one or more missions (in-memory)."""

    def __init__(self) -> None:
        self._events: list[TraceEvent] = []

    def append(self, event: TraceEvent) -> None:
        self._events.append(event)

    def timeline(self, mission_id: str) -> list[TraceEvent]:
        rows = [e for e in self._events if e.mission_id == mission_id]
        rows.sort(key=lambda e: (e.at,))
        return rows

    def by_run(self, run_id: str) -> list[TraceEvent]:
        return [e for e in self._events if e.run_id == run_id]

    def to_list(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self._events]


# ---- structured JSON logging (§59) -------------------------------------- #

_SENSITIVE_KEYS = (
    "token", "secret", "password", "passwd", "authorization", "auth",
    "cookie", "private_key", "privatekey", "session", "credential", "api_key", "apikey",
)

# The canonical structured-log field order.
LOG_FIELDS = (
    "timestamp", "severity", "component", "mission_id", "node_id", "run_id",
    "event", "message", "error_code", "duration_ms",
)


def _mask_sensitive_keys(fields: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in fields.items():
        low = key.lower()
        if any(marker in low for marker in _SENSITIVE_KEYS):
            out[key] = "[REDACTED]"
        else:
            out[key] = value
    return out


def format_log(fields: Mapping[str, Any]) -> str:
    """Render a structured, redacted JSON log line.

    Two layers of redaction: sensitive-named keys are masked, then the serialized
    line is run through the repo's value-pattern redaction (so a token that slips
    into a message string is still scrubbed).
    """
    masked = _mask_sensitive_keys(fields)
    # stable ordering: canonical fields first, then any extras sorted.
    ordered: dict[str, Any] = {}
    for f in LOG_FIELDS:
        if f in masked:
            ordered[f] = masked[f]
    for k in sorted(masked):
        if k not in ordered:
            ordered[k] = masked[k]
    line = json.dumps(ordered, ensure_ascii=False, default=str)
    return redact_sensitive_text(line, force=True)


__all__ = ["TraceEvent", "MissionTrace", "LOG_FIELDS", "format_log"]
