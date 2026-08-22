"""Privacy-preserving session recordings and deterministic replay assertions."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from pprint import pformat
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


Redactor = Callable[[dict[str, Any]], dict[str, Any]]
Clock = Callable[[], datetime]

_SESSION_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")
_WRITE_LOCK = threading.Lock()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sha256_json(value: Any) -> str:
    """Return a stable SHA-256 digest for a JSON-compatible value."""

    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _safe_session_id(session_id: str) -> str:
    normalized = _SESSION_ID_RE.sub("-", str(session_id).strip()).strip(".-")
    if not normalized:
        raise ValueError("session_id must contain at least one safe character")
    return normalized[:180]


@dataclass(frozen=True)
class RecordingConfig:
    enabled: bool = False
    retention_days: int = 30

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "RecordingConfig":
        raw = value or {}
        retention = raw.get("retention_days", 30)
        try:
            retention_days = max(1, int(retention))
        except (TypeError, ValueError):
            retention_days = 30
        return cls(enabled=raw.get("enabled") is True, retention_days=retention_days)


class SessionRecorder:
    """Append-only JSONL recorder that refuses to write unredacted data."""

    def __init__(
        self,
        config: RecordingConfig,
        root: str | Path,
        *,
        redactor: Redactor | None,
        clock: Clock = _utc_now,
    ) -> None:
        self.config = config
        self.root = Path(root)
        self.redactor = redactor
        self.clock = clock

    def append(
        self,
        session_id: str,
        event_type: str,
        payload: Mapping[str, Any],
        *,
        hash_fields: Iterable[str] = (),
        hash_only_fields: Iterable[str] = (),
    ) -> bool:
        if not self.config.enabled or self.redactor is None:
            return False

        raw_payload = dict(payload)
        all_hash_fields = tuple(dict.fromkeys((*hash_fields, *hash_only_fields)))
        hashes = {
            f"{field}_sha256": sha256_json(raw_payload[field])
            for field in all_hash_fields
            if field in raw_payload
        }

        try:
            redacted = self.redactor(raw_payload)
        except Exception:
            return False
        if not isinstance(redacted, dict):
            return False

        event = dict(redacted)
        for field in hash_only_fields:
            event.pop(field, None)
        event.update(hashes)
        event["t"] = str(event_type)
        event["at"] = self.clock().astimezone(timezone.utc).isoformat()

        try:
            safe_id = _safe_session_id(session_id)
            encoded = json.dumps(event, ensure_ascii=False, sort_keys=True, default=str)
            self.root.mkdir(parents=True, exist_ok=True)
            path = self.root / f"{safe_id}.jsonl"
            with _WRITE_LOCK, path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(encoded)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            try:
                path.chmod(0o600)
            except OSError:
                pass
            return True
        except (OSError, TypeError, ValueError):
            return False

    def prune(self) -> int:
        if not self.config.enabled or not self.root.exists():
            return 0

        cutoff = self.clock().astimezone(timezone.utc) - timedelta(
            days=self.config.retention_days
        )
        removed = 0
        for path in self.root.glob("*.jsonl"):
            try:
                modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
                if modified < cutoff:
                    path.unlink()
                    removed += 1
            except OSError:
                continue
        return removed


class ReplayAssertionError(AssertionError):
    """Raised when a replay differs from its recorded decisions."""


class SessionReplay:
    def __init__(self, events: Sequence[Mapping[str, Any]], source: Path) -> None:
        self.events = tuple(dict(event) for event in events)
        self.source = source

    @classmethod
    def load(cls, path: str | Path) -> "SessionReplay":
        source = Path(path)
        events: list[dict[str, Any]] = []
        with source.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"invalid JSONL at {source}:{line_number}: {exc.msg}"
                    ) from exc
                if not isinstance(event, dict) or not isinstance(event.get("t"), str):
                    raise ValueError(
                        f"invalid recording event at {source}:{line_number}"
                    )
                events.append(event)
        return cls(events, source)

    @property
    def tools(self) -> list[str]:
        return [
            str(event["tool"])
            for event in self.events
            if event.get("t") == "tool_call" and event.get("tool") is not None
        ]

    @property
    def approvals(self) -> list[str]:
        approvals: list[str] = []
        for event in self.events:
            if event.get("t") != "tool_call":
                continue
            approval = event.get("approval")
            if isinstance(approval, Mapping) and approval.get("verdict") is not None:
                approvals.append(str(approval["verdict"]))
        return approvals

    def assert_decisions(
        self,
        *,
        tools: Sequence[str] | None = None,
        approvals: Sequence[str] | None = None,
    ) -> None:
        drift: list[str] = []
        if tools is not None and list(tools) != self.tools:
            drift.append(
                f"tool sequence drift: expected {self.tools!r}, got {list(tools)!r}"
            )
        if approvals is not None and list(approvals) != self.approvals:
            drift.append(
                f"approval drift: expected {self.approvals!r}, got {list(approvals)!r}"
            )
        if drift:
            raise ReplayAssertionError("; ".join(drift))

    def emit_pytest(self, session_id: str) -> str:
        safe_name = re.sub(r"\W+", "_", session_id).strip("_") or "session"
        expected_tools = repr(self.tools)
        expected_approvals = repr(self.approvals)
        recorded_events = pformat(list(self.events), width=100, sort_dicts=True)
        return (
            "from pathlib import Path\n"
            "from agent.session_recording import SessionReplay\n\n"
            f"EXPECTED_TOOLS = {expected_tools}\n"
            f"EXPECTED_APPROVALS = {expected_approvals}\n\n"
            f"RECORDED_EVENTS = {recorded_events}\n\n"
            f"def test_replay_{safe_name}():\n"
            "    replay = SessionReplay(RECORDED_EVENTS, Path('<embedded-recording>'))\n"
            "    replay.assert_decisions(\n"
            "        tools=EXPECTED_TOOLS, approvals=EXPECTED_APPROVALS\n"
            "    )\n"
        )
