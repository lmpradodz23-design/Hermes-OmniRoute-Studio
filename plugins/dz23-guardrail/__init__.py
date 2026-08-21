"""Deterministic safety and verification gates for OmniRoute Studio."""

from __future__ import annotations

import json
import hashlib
import os
import re
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


_COMMAND_START = r"(?:^|(?:&&|\|\||[;&|\n]))\s*"
_COMMAND_TAIL = r"[^;&|\n]*"
_DESTRUCTIVE_PATTERNS = (
    (re.compile(_COMMAND_START + r"rm\b(?=" + _COMMAND_TAIL + r"(?:--recursive|-[a-z]*r))(?=" + _COMMAND_TAIL + r"(?:--force|-[a-z]*f))", re.IGNORECASE), "recursive forced rm"),
    (re.compile(_COMMAND_START + r"(?:del|erase)\b(?=" + _COMMAND_TAIL + r"/(?:s|q)\b)", re.IGNORECASE), "recursive Windows delete"),
    (re.compile(_COMMAND_START + r"(?:rd|rmdir)\b(?=" + _COMMAND_TAIL + r"/(?:s|q)\b)", re.IGNORECASE), "recursive Windows directory removal"),
    (re.compile(_COMMAND_START + r"remove-item\b(?=" + _COMMAND_TAIL + r"-(?:recurse|r)\b)(?=" + _COMMAND_TAIL + r"-(?:force|fo)\b)", re.IGNORECASE), "recursive forced Remove-Item"),
    (re.compile(_COMMAND_START + r"find\b" + _COMMAND_TAIL + r"(?:^|\s)-delete\b", re.IGNORECASE), "find -delete"),
    (re.compile(_COMMAND_START + r"git\s+clean\b(?=" + _COMMAND_TAIL + r"-[a-z]*f)", re.IGNORECASE), "forced git clean"),
    (re.compile(_COMMAND_START + r"git\s+reset\s+--hard\b", re.IGNORECASE), "git reset --hard"),
    (re.compile(_COMMAND_START + r"git\s+push\b" + _COMMAND_TAIL + r"(?:--force(?:-with-lease)?|-f)\b", re.IGNORECASE), "forced git push"),
    (re.compile(_COMMAND_START + r"(?:drop\s+(?:table|database)|truncate\s+(?:table\s+)?)\b", re.IGNORECASE), "destructive SQL"),
    (re.compile(_COMMAND_START + r"docker\s+(?:system|volume)\s+prune\b", re.IGNORECASE), "Docker prune"),
    (re.compile(_COMMAND_START + r"docker\s+image\s+prune\b" + _COMMAND_TAIL + r"(?:--all|-a)\b", re.IGNORECASE), "Docker image prune --all"),
    (re.compile(_COMMAND_START + r"docker\s+rm\b" + _COMMAND_TAIL + r"(?:--force|-f)\b", re.IGNORECASE), "forced Docker removal"),
    (re.compile(_COMMAND_START + r"(?:format-volume|clear-disk|takeown|vssadmin\s+delete\s+shadows|cipher\s+/w)\b", re.IGNORECASE), "destructive Windows administration"),
    (re.compile(_COMMAND_START + r"(?:reg(?:\.exe)?\s+delete|icacls\b" + _COMMAND_TAIL + r"/reset\b)", re.IGNORECASE), "destructive Windows security change"),
    (re.compile(r"\bshutil\.rmtree\s*\(", re.IGNORECASE), "shutil.rmtree"),
)
_WRITE_TOOLS = {"apply_patch", "edit_file", "file_write", "patch", "write_file"}
_VERIFY_PATTERN = re.compile(
    _COMMAND_START
    + r"(?:"
    + r"(?:pytest|tox|nox)\b|"
    + r"(?:python(?:\.exe)?\s+-m\s+pytest)\b|"
    + r"(?:uv\s+run\s+pytest)\b|"
    + r"(?:npm|pnpm|yarn|bun)\s+(?:test|run\s+(?:test|check|lint|typecheck|build|verify|e2e)\b)|"
    + r"(?:cargo|go|dotnet|mvn|gradle|playwright|vitest|jest)\s+(?:test|check|lint|typecheck|build|verify|e2e)\b|"
    + r"(?:tsc|ruff|mypy|eslint|biome)\b"
    + r")",
    re.IGNORECASE,
)
_TERMINAL_WRITE_PATTERN = re.compile(
    r"\b(?:copy-item|move-item|new-item|out-file|set-content|add-content|cp|mv|mkdir|touch|tee)\b|(?:^|[^>])>{1,2}(?!>)",
    re.IGNORECASE,
)
_PATCH_PATH_PATTERN = re.compile(
    r"^\*\*\*\s+(?:Add|Update|Delete) File:\s*(.+?)\s*$", re.MULTILINE
)
_state_lock = threading.Lock()
_verified_by_session: Dict[str, bool] = {}
_report_state_by_session: Dict[str, Dict[str, Any]] = {}


def _serialized(args: Any) -> str:
    try:
        return json.dumps(args, ensure_ascii=False, default=str)
    except Exception:
        return str(args)


def _command_text(args: Dict[str, Any]) -> str:
    """Return executable text without JSON quoting around its first token."""
    return "\n".join(
        value
        for key in ("command", "code", "script")
        if isinstance((value := args.get(key)), str)
    )


def _runtime_workspace() -> Optional[Path]:
    try:
        from agent.runtime_cwd import resolve_agent_cwd

        candidate = resolve_agent_cwd().expanduser().resolve(strict=False)
    except Exception:
        return None
    anchor = Path(candidate.anchor) if candidate.anchor else None
    if anchor is not None and candidate == anchor:
        return None
    return candidate


def _workspace_roots() -> tuple[Path, ...]:
    configured = os.environ.get("HERMES_GUARDRAIL_WORKSPACE_ROOTS", "")
    values = [value for value in configured.split(os.pathsep) if value.strip()]
    runtime_workspace = _runtime_workspace()
    if not values and runtime_workspace is not None:
        values.append(str(runtime_workspace))
    roots = []

    for value in values:
        try:
            root = Path(value).expanduser().resolve(strict=False)
        except Exception:
            continue
        if root not in roots:
            roots.append(root)

    return tuple(roots)


def _candidate_paths(tool_name: str, args: Dict[str, Any]) -> Iterable[Path]:
    for key in ("path", "file", "file_path", "target", "destination"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            yield Path(value.strip()).expanduser()

    if tool_name in {"apply_patch", "patch"}:
        patch_text = str(args.get("patch") or args.get("input") or "")
        for match in _PATCH_PATH_PATTERN.finditer(patch_text):
            yield Path(match.group(1).strip()).expanduser()

    if tool_name in {"terminal", "execute_code"} and _TERMINAL_WRITE_PATTERN.search(
        _command_text(args)
    ):
        for match in re.finditer(
            r"(?:[A-Za-z]:[\\/][^\s'\";|]+|/(?!workspace(?:/|\b))[^\s'\";|]+)",
            _command_text(args),
        ):
            yield Path(match.group(0)).expanduser()


def _resolved_candidate(path: Path, roots: tuple[Path, ...]) -> Path:
    if path.is_absolute():
        candidate = path
    else:
        runtime_workspace = _runtime_workspace()
        if runtime_workspace is not None and any(
            runtime_workspace == root or root in runtime_workspace.parents
            for root in roots
        ):
            candidate = runtime_workspace / path
        elif roots:
            candidate = roots[0] / path
        else:
            candidate = path
    try:
        return candidate.resolve(strict=False)
    except Exception:
        return candidate.absolute()


def _outside_workspace(path: Path) -> tuple[bool, Path]:
    roots = _workspace_roots()
    resolved = _resolved_candidate(path, roots)
    if not roots:
        return True, resolved

    for root in roots:
        try:
            resolved.relative_to(root)
            return False, resolved
        except ValueError:
            continue
    return True, resolved


def _command_detection_variants(command: str) -> Iterable[str]:
    from tools.approval import _command_detection_variants as core_variants

    return core_variants(command)


def _destructive_match(command: str) -> Optional[str]:
    for variant in _command_detection_variants(command):
        for pattern, label in _DESTRUCTIVE_PATTERNS:
            match = pattern.search(variant)
            if not match:
                continue
            if label == "forced git clean" and re.search(
                r"\bgit\s+clean\b[^;&|\n]*(?:--dry-run|-[a-z]*n)",
                match.group(0),
                re.IGNORECASE,
            ):
                continue
            return label
    return None


def _is_verification_command(command: str) -> bool:
    return any(_VERIFY_PATTERN.search(variant) for variant in _command_detection_variants(command))


def _verification_exit_code(result: Any, status: Any) -> Optional[int]:
    if str(status or "").strip().lower() in {"error", "failed", "blocked"}:
        return None
    candidate = result
    if isinstance(candidate, str):
        try:
            candidate = json.loads(candidate)
        except (TypeError, ValueError):
            return None
    if not isinstance(candidate, dict) or "exit_code" not in candidate:
        return None
    exit_code = candidate.get("exit_code")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        return None
    return exit_code


def _is_success(result: Any, status: Any) -> bool:
    if str(status or "").strip().lower() in {"error", "failed", "blocked"}:
        return False
    if isinstance(result, dict):
        return result.get("exit_code", 0) == 0 and not result.get("error")
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
        except (TypeError, ValueError):
            return "error" not in result.lower()
        return _is_success(parsed, status)
    return status in (None, "", "success", "completed")


def _session_key(session_id: str) -> str:
    return session_id or "default"


def _new_report_state() -> Dict[str, Any]:
    workspace = _runtime_workspace()
    return {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "workspace": str(workspace) if workspace is not None else "unresolved",
        "changed_paths": set(),
        "tools": set(),
        "subagents": [],
        "models": {},
        "cost_usd": 0.0,
    }


def _report_state(session_id: str) -> Dict[str, Any]:
    return _report_state_by_session.setdefault(
        _session_key(session_id), _new_report_state()
    )


def _report_root() -> Path:
    from hermes_constants import get_hermes_home

    return get_hermes_home() / "task-reports"


def _redact(value: str) -> str:
    try:
        from agent.redact import redact_sensitive_text

        return redact_sensitive_text(value, force=True)
    except Exception:
        return value


def _git_summary(workspace: Path) -> str:
    try:
        probe = subprocess.run(
            ["git", "-C", str(workspace), "rev-parse", "--show-toplevel"],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
        if probe.returncode != 0:
            return "Git summary unavailable (workspace is not a repository)."
        status = subprocess.run(
            ["git", "-C", str(workspace), "status", "--short"],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
        diff = subprocess.run(
            ["git", "-C", str(workspace), "diff", "--stat"],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
        parts = []
        if status.stdout.strip():
            parts.append("```text\n" + status.stdout.strip() + "\n```")
        if diff.stdout.strip():
            parts.append("```text\n" + diff.stdout.strip() + "\n```")
        return "\n\n".join(parts) or "Working tree clean."
    except (OSError, subprocess.SubprocessError):
        return "Git summary unavailable (git command failed)."


def _write_task_report(
    session_id: str, state: Dict[str, Any], outcome: Dict[str, Any]
) -> Optional[Path]:
    changed = sorted(
        str(path) for path in state.get("changed_paths", set()) if str(path).strip()
    )
    if not changed:
        return None

    workspace = (
        Path(str(state.get("workspace") or Path.cwd()))
        .expanduser()
        .resolve(strict=False)
    )
    tools = sorted(str(name) for name in state.get("tools", set()))
    subagents = list(state.get("subagents", []))
    models = dict(state.get("models", {}))
    completed = bool(outcome.get("completed")) and not bool(outcome.get("failed"))
    timestamp = datetime.now(timezone.utc)
    safe_session = (
        re.sub(r"[^A-Za-z0-9_.-]+", "-", _session_key(session_id)).strip("-")[:64]
        or "session"
    )
    report_dir = _report_root()
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = (
        report_dir / f"report-{timestamp.strftime('%Y%m%dT%H%M%SZ')}-{safe_session}.md"
    )

    model_lines = []
    for identity, usage in sorted(models.items()):
        model_lines.append(
            f"- {identity}: input={usage.get('input_tokens', 0)}, output={usage.get('output_tokens', 0)} tokens"
        )
    if not model_lines:
        model_lines.append("- No provider usage was reported by the runtime.")

    agent_lines = [
        f"- {row.get('role') or 'delegate'}: {row.get('status') or 'unknown'} ({row.get('duration_ms', 0)} ms)"
        for row in subagents
    ] or ["- No subagents were reported."]
    changed_lines = [f"- `{path}`" for path in changed]
    tool_line = (
        ", ".join(f"`{name}`" for name in tools) if tools else "No tools reported."
    )
    cost = float(state.get("cost_usd") or 0.0)

    body = "\n".join([
        "# Hermes OmniRoute Studio Task Report",
        "",
        f"- Session: `{_session_key(session_id)}`",
        f"- Started: {state.get('started_at')}",
        f"- Finished: {timestamp.isoformat()}",
        f"- Outcome: {'completed' if completed else 'incomplete or failed'}",
        f"- Workspace: `{workspace}`",
        f"- Auto-commit/push: disabled",
        "",
        "## Changed files",
        "",
        *changed_lines,
        "",
        "## Git review summary",
        "",
        _git_summary(workspace),
        "",
        "## Tools used",
        "",
        tool_line,
        "",
        "## Subagents",
        "",
        *agent_lines,
        "",
        "## Model usage",
        "",
        *model_lines,
        f"- Provider-reported cost captured: ${cost:.6f} USD"
        if cost
        else "- Monetary cost was not reported.",
        "",
        "## Review commands",
        "",
        "```text",
        "git diff --stat",
        "git diff -- <file>",
        "git add <approved-file>",
        "git restore --staged <file>",
        "```",
        "",
    ])
    temporary = report_path.with_suffix(".tmp")
    temporary.write_text(_redact(body), encoding="utf-8")
    temporary.replace(report_path)
    return report_path


def on_session_start(session_id: str = "", **_: Any) -> None:
    with _state_lock:
        _report_state_by_session[_session_key(session_id)] = _new_report_state()


def on_pre_tool_call(
    tool_name: str = "", args: Any = None, **_: Any
) -> Optional[Dict[str, str]]:
    safe_args = args if isinstance(args, dict) else {}
    executable = _command_text(safe_args)

    label = _destructive_match(executable) if executable else None
    if label:
        return {
            "action": "block",
            "message": f"DZ23 Guardrail blocked a destructive operation matching {label}.",
        }

    if tool_name in _WRITE_TOOLS or tool_name in {"terminal", "execute_code"}:
        outside = next(
            (
                resolved
                for path in _candidate_paths(tool_name, safe_args)
                for is_outside, resolved in [_outside_workspace(path)]
                if is_outside
            ),
            None,
        )
        if outside is not None:
            path_scope = hashlib.sha256(str(outside).encode("utf-8")).hexdigest()[:24]
            return {
                "action": "approve",
                "message": f"Writing outside the active workspace requires explicit approval: {outside}",
                "rule_key": f"outside-workspace:file:{path_scope}",
            }

    return None


def on_post_tool_call(
    tool_name: str = "",
    args: Any = None,
    result: Any = None,
    status: Any = None,
    session_id: str = "",
    **_: Any,
) -> None:
    key = _session_key(session_id)
    safe_args = args if isinstance(args, dict) else {}
    executable = _command_text(safe_args)

    with _state_lock:
        report = _report_state(session_id)
        report["tools"].add(tool_name or "unknown")
        requested_workdir = safe_args.get("workdir") or safe_args.get("cwd")
        if isinstance(requested_workdir, str) and requested_workdir.strip():
            report["workspace"] = requested_workdir.strip()
        if tool_name in _WRITE_TOOLS and _is_success(result, status):
            for path in _candidate_paths(tool_name, safe_args):
                report["changed_paths"].add(str(path))
        if tool_name in _WRITE_TOOLS and _is_success(result, status):
            _verified_by_session[key] = False
        elif tool_name in {"terminal", "execute_code"} and _is_verification_command(executable):
            exit_code = _verification_exit_code(result, status)
            _verified_by_session[key] = exit_code == 0


def on_pre_verify(
    session_id: str = "",
    coding: bool = False,
    changed_paths: Any = None,
    **_: Any,
) -> Optional[Dict[str, str]]:
    if not coding or not changed_paths:
        return None
    key = _session_key(session_id)
    with _state_lock:
        report = _report_state(session_id)
        if isinstance(changed_paths, (list, tuple, set)):
            report["changed_paths"].update(
                str(path) for path in changed_paths if str(path).strip()
            )
        verified = _verified_by_session.get(key, False)
    if verified:
        return None
    return {
        "action": "continue",
        "message": (
            "Verification evidence is missing after the latest code change. Run the project's relevant "
            "test, typecheck, lint, or build command; inspect its real output; fix failures before finishing."
        ),
    }


def on_post_api_request(
    session_id: str = "",
    provider: str = "",
    model: str = "",
    usage: Any = None,
    cost_usd: Any = None,
    **_: Any,
) -> None:
    usage_dict = usage if isinstance(usage, dict) else {}
    identity = f"{provider or 'unknown'}/{model or 'unknown'}"
    with _state_lock:
        report = _report_state(session_id)
        aggregate = report["models"].setdefault(
            identity, {"input_tokens": 0, "output_tokens": 0}
        )
        for field in ("input_tokens", "output_tokens"):
            value = usage_dict.get(field, 0)
            if isinstance(value, (int, float)):
                aggregate[field] += int(value)
        if isinstance(cost_usd, (int, float)):
            report["cost_usd"] += float(cost_usd)


def on_subagent_stop(
    parent_session_id: str = "",
    child_role: str = "",
    child_status: str = "",
    duration_ms: Any = 0,
    **_: Any,
) -> None:
    with _state_lock:
        _report_state(parent_session_id)["subagents"].append({
            "role": child_role or "delegate",
            "status": child_status or "unknown",
            "duration_ms": int(duration_ms)
            if isinstance(duration_ms, (int, float))
            else 0,
        })


def on_session_end(
    session_id: str = "",
    completed: bool = False,
    failed: bool = False,
    interrupted: bool = False,
    **_: Any,
) -> None:
    key = _session_key(session_id)
    with _state_lock:
        state = _report_state_by_session.pop(key, None)
        _verified_by_session.pop(key, None)
    if state is None:
        return
    try:
        _write_task_report(
            session_id,
            state,
            {"completed": completed, "failed": failed, "interrupted": interrupted},
        )
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        # Reporting is an audit aid. It must never prevent session teardown.
        return


def register(ctx: Any) -> None:
    ctx.register_hook("on_session_start", on_session_start)
    ctx.register_hook("pre_tool_call", on_pre_tool_call)
    ctx.register_hook("post_tool_call", on_post_tool_call)
    ctx.register_hook("pre_verify", on_pre_verify)
    ctx.register_hook("post_api_request", on_post_api_request)
    ctx.register_hook("subagent_stop", on_subagent_stop)
    ctx.register_hook("on_session_end", on_session_end)
