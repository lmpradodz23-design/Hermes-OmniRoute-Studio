"""Inspect and validate privacy-preserving Hermes session recordings."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from agent.session_recording import SessionReplay


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

    if getattr(args, "against_model", None):
        print(
            "Replay safety: this command does not execute recorded tools against a model. "
            "Use --emit-test for a deterministic regression fixture.",
            file=sys.stderr,
        )
        return 2

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
