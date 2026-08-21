"""Keyless daily OmniRoute health summary for Hermes cron."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path


MODELS_URL = "http://127.0.0.1:20128/v1/models"
LEVEL_PATTERN = re.compile(r"\b(error|fatal|warn(?:ing)?)\b", re.IGNORECASE)


def _tail(path: Path, max_lines: int = 500) -> list[str]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return handle.readlines()[-max_lines:]


def _model_count() -> int:
    request = urllib.request.Request(MODELS_URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.load(response)
    models = payload.get("data", []) if isinstance(payload, dict) else []
    return len(models) if isinstance(models, list) else 0


def main() -> int:
    omni_home = Path(os.environ.get("OMNIROUTE_HOME") or Path.home() / ".omniroute")
    log_path = omni_home / "logs" / "application" / "app.log"
    storage_path = omni_home / "storage.sqlite"
    lines = _tail(log_path)
    levels = {"errors": 0, "warnings": 0}

    for line in lines:
        for match in LEVEL_PATTERN.finditer(line):
            level = match.group(1).lower()
            levels["errors" if level in {"error", "fatal"} else "warnings"] += 1

    try:
        models = _model_count()
        gateway = f"online ({models} models advertised)"
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
        gateway = f"offline or invalid response ({type(exc).__name__})"

    storage_mb = storage_path.stat().st_size / (1024 * 1024) if storage_path.is_file() else 0.0
    print("OmniRoute daily health")
    print(f"- Gateway: {gateway}")
    print(f"- Recent log window: {len(lines)} lines, {levels['errors']} errors, {levels['warnings']} warnings")
    print(f"- Local database: {storage_mb:.1f} MiB")
    return 0 if gateway.startswith("online") else 1


if __name__ == "__main__":
    raise SystemExit(main())
