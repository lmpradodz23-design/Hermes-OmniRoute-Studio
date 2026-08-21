"""Keyless, structured daily OmniRoute health summary for Hermes cron."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULTS_PATH = Path(__file__).with_name("omniroute-defaults.json")
LOG_LEVEL_PATTERN = re.compile(
    r"^(?:\d{4}-\d{2}-\d{2}[T ][^ ]+\s+)?(?:\[[^\]]+\]\s*)?\[?(fatal|error|warn(?:ing)?)\]?\b",
    re.IGNORECASE,
)


def _load_defaults() -> dict[str, str]:
    payload = json.loads(DEFAULTS_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("base_url"), str):
        raise ValueError("OmniRoute defaults do not define base_url")
    return payload


def models_url() -> str:
    base_url = (os.environ.get("OMNIROUTE_BASE_URL") or _load_defaults()["base_url"]).rstrip("/")
    return f"{base_url}/models"


def _tail(path: Path, max_lines: int = 500) -> list[str]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return handle.readlines()[-max_lines:]


def parse_log_level(line: str) -> str | None:
    """Return one normalized severity per log event, never keyword-count prose."""
    try:
        payload: Any = json.loads(line)
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = None

    if isinstance(payload, dict):
        for key in ("level", "severity", "levelname"):
            value = str(payload.get(key, "")).lower()
            if value in {"fatal", "error"}:
                return "error"
            if value in {"warn", "warning"}:
                return "warning"

    match = LOG_LEVEL_PATTERN.search(line.strip())
    if not match:
        return None
    return "error" if match.group(1).lower() in {"fatal", "error"} else "warning"


def summarize_log_levels(lines: list[str]) -> dict[str, int]:
    levels = {"errors": 0, "warnings": 0}
    for line in lines:
        level = parse_log_level(line)
        if level:
            levels[f"{level}s"] += 1
    return levels


def _model_count(url: str | None = None) -> int:
    request = urllib.request.Request(url or models_url(), headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.load(response)
    models = payload.get("data", []) if isinstance(payload, dict) else []
    if not isinstance(models, list):
        raise ValueError("models data is not a list")
    return len(models)


def build_health_summary(*, omni_home: Path | None = None) -> dict[str, Any]:
    home = omni_home or Path(os.environ.get("OMNIROUTE_HOME") or Path.home() / ".omniroute")
    log_path = home / "logs" / "application" / "app.log"
    storage_path = home / "storage.sqlite"
    lines = _tail(log_path)
    levels = summarize_log_levels(lines)
    gateway: dict[str, Any]

    try:
        gateway = {"status": "online", "models_advertised": _model_count()}
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
        gateway = {"status": "offline", "error_type": type(exc).__name__}

    return {
        "gateway": gateway,
        "log_window": {"lines": len(lines), **levels},
        "storage_mib": round(storage_path.stat().st_size / (1024 * 1024), 1) if storage_path.is_file() else 0.0,
    }


def main() -> int:
    summary = build_health_summary()
    if "--json" in sys.argv[1:]:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    else:
        gateway = summary["gateway"]
        gateway_text = (
            f"online ({gateway['models_advertised']} models advertised)"
            if gateway["status"] == "online"
            else f"offline or invalid response ({gateway['error_type']})"
        )
        logs = summary["log_window"]
        print("OmniRoute daily health")
        print(f"- Gateway: {gateway_text}")
        print(f"- Recent log window: {logs['lines']} lines, {logs['errors']} errors, {logs['warnings']} warnings")
        print(f"- Local database: {summary['storage_mib']:.1f} MiB")
    return 0 if summary["gateway"]["status"] == "online" else 1


if __name__ == "__main__":
    raise SystemExit(main())
