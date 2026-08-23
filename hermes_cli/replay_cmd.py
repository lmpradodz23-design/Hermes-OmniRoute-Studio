"""Inspect and validate privacy-preserving Hermes session recordings."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from agent.session_recording import SessionReplay


def _run_model_probe(
    replay: SessionReplay, model: str
) -> tuple[list[str], list[str], str]:
    starts = [event for event in replay.events if event.get("t") == "turn_start"]
    prompt = str(starts[0].get("user_message") or "") if starts else ""
    if not prompt:
        raise ValueError(
            "recording has no redacted user_message; record a new opted-in session"
        )

    prior_approvals = replay.approvals
    max_turns = max(2, min(len(replay.tools) + 2, 12))
    with tempfile.TemporaryDirectory(prefix="hermes-replay-") as temporary:
        capture = Path(temporary) / "decisions.jsonl"
        # `os.environ.copy()` cru perde a propagação de HERMES_HOME/HOME que
        # todo spawn do Hermes precisa — o guard em
        # tests/agent/test_subprocess_env_guard.py existe porque isso já foi
        # corrigido site a site umas onze vezes. `scrub_secrets=False` mantém o
        # comportamento anterior: o filho é o próprio Hermes, rodando o mesmo
        # perfil, e precisa das credenciais do modelo.
        from tools.environments.local import build_subprocess_env

        env = build_subprocess_env(
            scrub_secrets=False,
            extra={
                "HERMES_REPLAY_DECISION_CAPTURE": str(capture),
                "HERMES_REPLAY_APPROVALS_JSON": json.dumps(prior_approvals),
            },
        )
        command = [
            sys.executable,
            "-m",
            "hermes_cli.main",
            "chat",
            "--query",
            prompt,
            "--model",
            model,
            "--max-turns",
            str(max_turns),
            "--run-budget",
            "120",
            "--quiet",
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=150,
            check=False,
        )
        events = []
        if capture.exists():
            for line in capture.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    event = json.loads(line)
                    if isinstance(event, dict):
                        events.append(event)
        if not events and completed.returncode != 0:
            diagnostic = (completed.stderr or "model probe failed").strip().splitlines()
            raise RuntimeError(diagnostic[-1] if diagnostic else "model probe failed")

    return (
        [str(event.get("tool") or "unknown") for event in events],
        [str(event.get("approval") or "") for event in events],
        model,
    )


def _decision_diff(recorded: list[str], current: list[str], *, label: str) -> list[str]:
    width = max(len(recorded), len(current))
    rows: list[str] = []
    for index in range(width):
        before = recorded[index] if index < len(recorded) else "<none>"
        after = current[index] if index < len(current) else "<none>"
        marker = "=" if before == after else "->"
        rows.append(f"- {label}[{index + 1}]: {before} {marker} {after}")
    return rows


def _runtime_approval_verdicts(replay: SessionReplay) -> list[str]:
    """Re-evaluate recorded tool inputs against today's authorization hooks.

    This is intentionally authorization-only: it never executes a tool and it
    never opens a human prompt. When the current policy still requires human
    approval, the recorded human answer is retained so policy drift and user
    choice remain distinct facts.
    """
    from hermes_cli.plugins import _get_pre_tool_call_directive_details

    verdicts: list[str] = []
    for event in replay.events:
        if event.get("t") != "tool_call":
            continue
        args = event.get("args_redacted", event.get("args", {}))
        safe_args = args if isinstance(args, dict) else {}
        details = _get_pre_tool_call_directive_details(
            str(event.get("tool") or "unknown"),
            safe_args,
            session_id="replay-policy-audit",
            tool_call_id=str(event.get("tool_call_id") or ""),
            turn_id=str(event.get("turn_id") or event.get("turn") or ""),
        )
        recorded = event.get("approval")
        prior = str(recorded.get("verdict") or "") if isinstance(recorded, dict) else ""
        if details.action == "block":
            verdicts.append("blocked")
        elif details.action == "approve":
            verdicts.append(
                prior if prior in {"approved", "denied"} else "confirmation_required"
            )
        else:
            verdicts.append("automatic")
    return verdicts


def _recording_root(args: Any) -> Path:
    override = getattr(args, "recordings_dir", None)
    if override:
        return Path(override).expanduser().resolve(strict=False)
    from hermes_constants import get_hermes_home

    return get_hermes_home() / "session-recordings"


def _recording_path(root: Path, session_id: str) -> Path:
    candidate = str(session_id or "").strip()
    if not candidate or any(part in candidate for part in ("/", "\\", "..")):
        raise ValueError("session id must be a file-safe identifier")
    return root / f"{candidate}.jsonl"


def _validate_integrity(replay: SessionReplay, args: Any) -> list[str]:
    errors: list[str] = []
    tool_calls = [event for event in replay.events if event.get("t") == "tool_call"]
    tool_results = [event for event in replay.events if event.get("t") == "tool_result"]
    if getattr(args, "assert_tools", False):
        call_tools = [str(event.get("tool") or "") for event in tool_calls]
        result_tools = [str(event.get("tool") or "") for event in tool_results]
        if call_tools != result_tools:
            errors.append(
                f"tool sequence mismatch: calls={call_tools!r}, results={result_tools!r}"
            )
    if getattr(args, "assert_approvals", False):
        for index, event in enumerate(tool_calls, start=1):
            approval = event.get("approval")
            verdict = approval.get("verdict") if isinstance(approval, dict) else None
            if verdict not in {
                "automatic",
                "confirmation_required",
                "approved",
                "blocked",
                "denied",
            }:
                errors.append(f"tool call {index} has missing approval verdict")
        if not errors:
            current = _runtime_approval_verdicts(replay)
            if current != replay.approvals:
                errors.append(
                    f"approval verdict drift: recorded={replay.approvals!r}, current={current!r}"
                )
    return errors


def cmd_replay(args: argparse.Namespace) -> int:
    try:
        source = _recording_path(_recording_root(args), args.session_id)
        replay = SessionReplay.load(source)
    except (OSError, ValueError) as exc:
        print(f"Replay error: {exc}", file=sys.stderr)
        return 2

    against_model = getattr(args, "against_model", None)
    if against_model:
        try:
            tools, approvals, route = _run_model_probe(replay, against_model)
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            print(f"Replay model probe failed: {exc}", file=sys.stderr)
            return 2
        tool_diff = _decision_diff(replay.tools, tools, label="tool")
        approval_diff = _decision_diff(replay.approvals, approvals, label="approval")
        print(f"Model decision diff: recorded -> {route}")
        print("\n".join((*tool_diff, *approval_diff)))
        if getattr(args, "assert_tools", False) and tools != replay.tools:
            return 2
        if getattr(args, "assert_approvals", False) and approvals != replay.approvals:
            return 2
        return 0

    errors = _validate_integrity(replay, args)
    if errors:
        for error in errors:
            print(f"Replay drift: {error}", file=sys.stderr)
        return 2

    emit_test = getattr(args, "emit_test", None)
    if emit_test:
        emitted = replay.emit_pytest(args.session_id)
        if emit_test == "-":
            print(emitted, end="")
            return 0
        destination = Path(emit_test).expanduser().resolve(strict=False)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(emitted, encoding="utf-8")
        print(f"Generated replay test: {destination}")

    count = len(replay.tools)
    print(f"Replay valid: {count} tool call{'s' if count != 1 else ''}.")
    if getattr(args, "assert_approvals", False):
        print("approval evidence: valid")
    return 0


def build_replay_parser(subparsers, *, cmd_replay_handler=cmd_replay):
    parser = subparsers.add_parser(
        "replay",
        help="Validate an opt-in redacted session recording",
        description=(
            "Validate tool/result and approval evidence from an append-only "
            "session recording, or generate a pytest regression fixture."
        ),
    )
    parser.add_argument("session_id", help="Recorded session identifier")
    parser.add_argument("--against-model", metavar="MODEL")
    parser.add_argument("--assert-tools", action="store_true")
    parser.add_argument("--assert-approvals", action="store_true")
    parser.add_argument(
        "--emit-test",
        nargs="?",
        const="-",
        metavar="PATH",
        help="Print a pytest fixture to stdout, or write it to PATH",
    )
    parser.set_defaults(func=cmd_replay_handler)
    return parser
