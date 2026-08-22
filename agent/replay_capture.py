"""Decision-only capture used by ``hermes replay --against-model``."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any


_lock = threading.Lock()
_approval_index = 0


def reset_capture_state() -> None:
    global _approval_index
    with _lock:
        _approval_index = 0


def _capture_path() -> Path | None:
    raw = os.environ.get("HERMES_REPLAY_DECISION_CAPTURE", "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.is_absolute() else None


def _recorded_approvals() -> list[str]:
    raw = os.environ.get("HERMES_REPLAY_APPROVALS_JSON", "[]")
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def capture_authorization(details: Any, tool_name: str) -> str | None:
    """Capture a policy decision and return a block that prevents execution."""
    destination = _capture_path()
    if destination is None:
        return None

    global _approval_index
    with _lock:
        action = str(getattr(details, "action", None) or "")
        path = str(getattr(details, "rule_key", None) or "runtime")
        if action == "block":
            verdict = "blocked"
        elif action == "approve":
            prior = _recorded_approvals()
            verdict = (
                prior[_approval_index]
                if _approval_index < len(prior)
                and prior[_approval_index] in {"approved", "denied"}
                else "confirmation_required"
            )
        else:
            verdict = "automatic"
        _approval_index += 1

        event = {
            "tool": str(tool_name or "unknown"),
            "approval": verdict,
            "approval_path": path,
        }
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            destination.chmod(0o600)
        except OSError:
            pass

    return "REPLAY_CAPTURE: decision recorded; tool execution is disabled."
