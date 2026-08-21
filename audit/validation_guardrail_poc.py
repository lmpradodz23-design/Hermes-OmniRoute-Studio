"""Safe, non-executing reproducer for DZ23 guardrail audit findings."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_PATH = REPO_ROOT / "plugins" / "dz23-guardrail" / "__init__.py"


def load_plugin():
    spec = importlib.util.spec_from_file_location("dz23_guardrail_poc", PLUGIN_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load guardrail from {PLUGIN_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    plugin = load_plugin()
    cases = {
        "posix_destructive": plugin.on_pre_tool_call(
            "terminal", {"command": "rm -rf /tmp/teste"}
        ),
        "windows_destructive": plugin.on_pre_tool_call(
            "terminal", {"command": r"del /s /q C:\\temp\\teste"}
        ),
        "relative_outside_candidate": plugin.on_pre_tool_call(
            "write_file", {"path": "..\\outside.txt"}
        ),
        "documentation_false_positive": plugin.on_pre_tool_call(
            "write_file",
            {
                "path": "audit/example.md",
                "content": "Never run rm -rf / on a workstation.",
            },
        ),
    }

    session = "guardrail-poc"
    plugin.on_session_start(session_id=session)
    plugin.on_post_tool_call(
        tool_name="write_file",
        args={"path": "src/example.py"},
        result={"exit_code": 0},
        status="success",
        session_id=session,
    )
    plugin.on_post_tool_call(
        tool_name="terminal",
        args={"command": "echo npm test"},
        result="the command did not run",
        status="success",
        session_id=session,
    )
    cases["forged_verification"] = plugin.on_pre_verify(
        session_id=session,
        coding=True,
        changed_paths=["src/example.py"],
    )

    print(json.dumps(cases, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
