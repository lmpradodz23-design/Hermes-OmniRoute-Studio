from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "integrations" / "omniroute-daily-health.py"
SPEC = importlib.util.spec_from_file_location("omniroute_daily_health", MODULE_PATH)
health = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(health)


def test_models_url_comes_from_shared_desktop_defaults(monkeypatch):
    monkeypatch.delenv("OMNIROUTE_BASE_URL", raising=False)
    defaults = json.loads((ROOT / "integrations" / "omniroute-defaults.json").read_text(encoding="utf-8"))
    preset = (ROOT / "apps" / "desktop" / "src" / "app" / "settings" / "omniroute-preset.ts").read_text(
        encoding="utf-8"
    )

    assert "omniroute-defaults.json" in preset
    assert health.models_url() == f"{defaults['base_url']}/models"


def test_log_summary_counts_one_structured_severity_per_event():
    lines = [
        '{"level":"error","message":"error error warn in user prose"}',
        '{"severity":"warning","message":"error word is not the event level"}',
        "2026-08-21T12:00:00Z ERROR request failed; warning text follows",
        "INFO user wrote error fatal warning in a prompt",
    ]

    assert health.summarize_log_levels(lines) == {"errors": 2, "warnings": 1}


def test_health_summary_is_structured_and_redacts_exception_message(tmp_path, monkeypatch):
    secret = "token-must-not-appear"

    def fail():
        raise OSError(secret)

    monkeypatch.setattr(health, "_model_count", fail)
    summary = health.build_health_summary(omni_home=tmp_path)

    assert summary["gateway"] == {"status": "offline", "error_type": "OSError"}
    assert secret not in json.dumps(summary)
    assert summary["log_window"] == {"lines": 0, "errors": 0, "warnings": 0}
