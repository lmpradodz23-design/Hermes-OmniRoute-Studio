"""Deterministic safety and verification gates for OmniRoute Studio."""

import json
import hashlib
import os
import re
import shutil
import subprocess
import threading
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, Optional


_COMMAND_START = r"(?:^|(?:&&|\|\||[;&|\n]))\s*"
_COMMAND_TAIL = r"[^;&|\n]*"
_DESTRUCTIVE_PATTERNS = (
    (
        re.compile(
            _COMMAND_START
            + r"rm\b(?="
            + _COMMAND_TAIL
            + r"(?:--recursive|-[a-z]*r))(?="
            + _COMMAND_TAIL
            + r"(?:--force|-[a-z]*f))",
            re.IGNORECASE,
        ),
        "recursive forced rm",
    ),
    (
        re.compile(
            _COMMAND_START + r"(?:del|erase)\b(?=" + _COMMAND_TAIL + r"/(?:s|q)\b)",
            re.IGNORECASE,
        ),
        "recursive Windows delete",
    ),
    (
        re.compile(
            _COMMAND_START + r"(?:rd|rmdir)\b(?=" + _COMMAND_TAIL + r"/(?:s|q)\b)",
            re.IGNORECASE,
        ),
        "recursive Windows directory removal",
    ),
    (
        re.compile(
            _COMMAND_START
            + r"remove-item\b(?="
            + _COMMAND_TAIL
            + r"-(?:recurse|r)\b)(?="
            + _COMMAND_TAIL
            + r"-(?:force|fo)\b)",
            re.IGNORECASE,
        ),
        "recursive forced Remove-Item",
    ),
    (
        re.compile(
            _COMMAND_START + r"find\b" + _COMMAND_TAIL + r"(?:^|\s)-delete\b",
            re.IGNORECASE,
        ),
        "find -delete",
    ),
    (
        re.compile(
            _COMMAND_START + r"git\s+clean\b(?=" + _COMMAND_TAIL + r"-[a-z]*f)",
            re.IGNORECASE,
        ),
        "forced git clean",
    ),
    (
        re.compile(_COMMAND_START + r"git\s+reset\s+--hard\b", re.IGNORECASE),
        "git reset --hard",
    ),
    (
        re.compile(
            _COMMAND_START
            + r"git\s+push\b"
            + _COMMAND_TAIL
            + r"(?:--force(?:-with-lease)?|-f)\b",
            re.IGNORECASE,
        ),
        "forced git push",
    ),
    (
        re.compile(
            _COMMAND_START
            + r"(?:drop\s+(?:table|database)|truncate\s+(?:table\s+)?)\b",
            re.IGNORECASE,
        ),
        "destructive SQL",
    ),
    (
        re.compile(
            _COMMAND_START + r"docker\s+(?:system|volume)\s+prune\b", re.IGNORECASE
        ),
        "Docker prune",
    ),
    (
        re.compile(
            _COMMAND_START
            + r"docker\s+image\s+prune\b"
            + _COMMAND_TAIL
            + r"(?:--all|-a)\b",
            re.IGNORECASE,
        ),
        "Docker image prune --all",
    ),
    (
        re.compile(
            _COMMAND_START + r"docker\s+rm\b" + _COMMAND_TAIL + r"(?:--force|-f)\b",
            re.IGNORECASE,
        ),
        "forced Docker removal",
    ),
    (
        re.compile(
            _COMMAND_START
            + r"(?:format-volume|clear-disk|takeown|vssadmin\s+delete\s+shadows|cipher\s+/w)\b",
            re.IGNORECASE,
        ),
        "destructive Windows administration",
    ),
    (
        re.compile(
            _COMMAND_START
            + r"(?:reg(?:\.exe)?\s+delete|icacls\b"
            + _COMMAND_TAIL
            + r"/reset\b)",
            re.IGNORECASE,
        ),
        "destructive Windows security change",
    ),
    (re.compile(r"\bshutil\.rmtree\s*\(", re.IGNORECASE), "shutil.rmtree"),
    (
        re.compile(
            _COMMAND_START
            + r"(?:powershell|pwsh)(?:\.exe)?\b"
            + _COMMAND_TAIL
            + r"\s-(?:encodedcommand|enc|e)\b",
            re.IGNORECASE,
        ),
        "encoded PowerShell command",
    ),
    (
        re.compile(
            r"\b(?:base64|base32|base16)\s+(?:-[dD]|--decode)\b[^|]*\|\s*(?:bash|sh|zsh|ksh|dash)\b",
            re.IGNORECASE,
        ),
        "encoded command piped to a shell",
    ),
    (
        re.compile(_COMMAND_START + r"(?:invoke-expression|iex)\b", re.IGNORECASE),
        "PowerShell dynamic command execution",
    ),
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
_state_lock = threading.RLock()
_verified_by_session: Dict[str, bool] = {}
_report_state_by_session: Dict[str, Dict[str, Any]] = {}


@dataclass(frozen=True)
class TaintMark:
    source: str
    detail: str
    tool: str
    turn: int
    at: str


_taint_by_session: Dict[str, Deque[TaintMark]] = {}
_turn_by_session: Dict[str, int] = {}
_TAINT_SOURCES = frozenset({
    "web",
    "external-file",
    "memory",
    "mcp-external",
    "installed-skill",
})
_WEB_TOOLS = frozenset({
    "omniroute_web_fetch",
    "omniroute_web_search",
    "omniroute_oneproxy_fetch",
    "fetch_link_title",
    "web_fetch",
    "web_search",
    "web_extract",
})
_MEMORY_TOOLS = frozenset({
    "omniroute_memory_search",
    "memory_search",
    "memory_recall",
    "recall_memory",
})
_INSTALLED_SKILL_TOOLS = frozenset({
    "omniroute_github_skills_install",
    "omniroute_skills_execute",
})
_EXTERNAL_FILE_TOOLS = frozenset({
    "local_corpus_read",
    "obsidian_read_note",
    "notion_get_page",
    "notion_query_database",
})
_PRIVILEGED_TOOLS = frozenset({
    "plugin_install",
    "plugin_activate",
    "omniroute_skills_enable",
    "omniroute_github_skills_install",
    "omniroute_memory_add",
    "memory_write",
    "write_memory",
})
_SENSITIVE_PATH_PATTERN = re.compile(
    r"(?:^|[\\/])(?:\.env(?:\.[^\\/]+)?|\.ssh|\.aws|\.azure|\.config[\\/]gcloud|credentials?|secrets?|id_(?:rsa|ed25519)|auth\.json)(?:$|[\\/])",
    re.IGNORECASE,
)
_NETWORK_COMMAND_PATTERN = re.compile(
    r"(?:^|\s)(?:curl|wget|invoke-webrequest|iwr|invoke-restmethod|irm)\b|\brequests\.(?:get|post|put|patch|delete)\s*\(",
    re.IGNORECASE,
)
_REMOTE_COMMAND_PATTERN = re.compile(
    r"(?:^|\s)(?:ssh|scp|sftp|rsync)\b|\bgit\s+(?:push|remote\s+add)\b",
    re.IGNORECASE,
)
_PREFIX_WRAPPER_PATTERN = re.compile(
    r"(?P<boundary>^|(?:&&|\|\||[;&|\n]))\s*"
    r"(?:(?:sudo(?:\s+--?[^\s;&|]+)*|env(?:\s+(?:--?[^\s;&|]+|[A-Za-z_][A-Za-z0-9_]*=[^\s;&|]+))*|[A-Za-z_][A-Za-z0-9_]*=[^\s;&|]+)\s+)+",
    re.IGNORECASE,
)
_EXECUTION_WRAPPER_PATTERNS = (
    re.compile(
        r"\b(?:bash|sh|zsh|ksh|dash)\b[^;&|\n]*?\s-(?:c|lc)\s+(?:\"([^\"]*)\"|'([^']*)'|([^;&|\n]+))",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bcmd(?:\.exe)?\b(?:\s+/[^\s;&|]+)*\s+/(?:c|k)\s+(?:\"([^\"]*)\"|'([^']*)'|([^;&|\n]+))",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:powershell|pwsh)(?:\.exe)?\b[^;&|\n]*?\s-(?:command|c)\s+(?:\"([^\"]*)\"|'([^']*)'|([^;&|\n]+))",
        re.IGNORECASE,
    ),
    # Command substitution executes its payload, but the payload does not sit at
    # a command boundary, so _COMMAND_START never anchors on it. Surface the
    # inner command so the destructive patterns can inspect it.
    re.compile(r"\$\(\s*([^()]+?)\s*\)"),
    re.compile(r"`\s*([^`]+?)\s*`"),
)
_MAX_GUARDRAIL_VARIANTS = 64
_MAX_GUARDRAIL_COMMAND_CHARS = 131_072
_SPEND_CEILING_REFERENCE = re.compile(
    r"(?:security[.:'\"/\\-]*spend_ceiling|\bspend_ceiling\b)",
    re.IGNORECASE,
)
_SENSITIVE_RECORDING_KEY = re.compile(
    r"^(?:api[_-]?key|token|access[_-]?token|refresh[_-]?token|secret|password|authorization|cookie|credential)s?$",
    re.IGNORECASE,
)


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


def _mutates_user_spend_ceiling(tool_name: str, args: Dict[str, Any]) -> bool:
    """Detect model-authored mutations of the owner-only local cost policy."""
    serialized = _serialized(args)
    if not _SPEND_CEILING_REFERENCE.search(serialized):
        return False
    if tool_name in {"terminal", "execute_code"}:
        executable = _command_text(args)
        return bool(
            re.search(r"\bhermes\s+config\s+(?:set|unset|edit)\b", executable, re.I)
            or re.search(r"(?:^|[\\/])\.hermes[\\/]config\.ya?ml\b", executable, re.I)
        )
    if tool_name not in _WRITE_TOOLS:
        return False
    return any(
        path.name.casefold() in {"config.yaml", "config.yml"}
        and ".hermes" in {part.casefold() for part in path.parts}
        for path in _candidate_paths(tool_name, args)
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


# Shell tokens that vanish at execution time and therefore must not hide a
# destructive verb from the patterns: ``r\\m`` and ``r''m`` both run ``rm``.
_EMPTY_QUOTE_PAIR = re.compile(r"(?:''|\"\")")
_INERT_BACKSLASH_ESCAPE = re.compile(r"\\(?=[^\s\\])")


def _standalone_detection_variants(command: str) -> tuple[str, ...]:
    """Normalize the shell tricks the shared parser would have removed.

    Only ever ADDS variants — the raw command is always kept first, so a
    Windows path (``C:\\Users\\me``) is still inspected verbatim even though
    the unescaped form mangles it. ``_destructive_match`` blocks when ANY
    variant matches, so widening the set can only tighten the gate.
    """
    raw = str(command or "")
    variants = [raw]
    for candidate in (
        _EMPTY_QUOTE_PAIR.sub("", raw),
        _INERT_BACKSLASH_ESCAPE.sub("", _EMPTY_QUOTE_PAIR.sub("", raw)),
    ):
        if candidate and candidate not in variants:
            variants.append(candidate)
    return tuple(variants)


def _command_detection_variants(command: str) -> Iterable[str]:
    try:
        from tools.approval import _command_detection_variants as core_variants

        return core_variants(command)
    except Exception:
        # Standalone fallback. The previous implementation returned the raw
        # command only, which the fuzz corpus proves is NOT conservative:
        # `r\\m -rf`, `r''m -rf`, `$(rm -rf ...)` and backtick substitution all
        # escaped while this path was active. Normalize locally instead, so a
        # missing shared parser degrades detection quality without opening a
        # hole. The security-critical plugin manager still fails closed if this
        # plugin raises.
        return _standalone_detection_variants(command)


def _guardrail_detection_variants(command: str) -> Iterable[str]:
    """Yield bounded core variants plus executable payloads from common wrappers."""
    raw = str(command or "")
    if len(raw) > _MAX_GUARDRAIL_COMMAND_CHARS:
        # Oversized executable text is not safe to parse optimistically. The
        # sentinel is matched below and keeps the hook deterministic.
        yield "guardrail-oversized-command"
        return

    pending = deque(_command_detection_variants(raw))
    seen = set()

    while pending and len(seen) < _MAX_GUARDRAIL_VARIANTS:
        variant = str(pending.popleft()).strip()
        if not variant or variant in seen:
            continue
        seen.add(variant)
        yield variant

        without_prefix_wrappers = _PREFIX_WRAPPER_PATTERN.sub(
            lambda match: match.group("boundary") + " ", variant
        ).strip()
        if without_prefix_wrappers and without_prefix_wrappers not in seen:
            pending.append(without_prefix_wrappers)

        for pattern in _EXECUTION_WRAPPER_PATTERNS:
            for match in pattern.finditer(variant):
                payload = next(
                    (group for group in match.groups() if group is not None), ""
                ).strip()
                if payload and payload not in seen:
                    pending.append(payload)


def _destructive_match(command: str) -> Optional[str]:
    for variant in _guardrail_detection_variants(command):
        if variant == "guardrail-oversized-command":
            return "oversized executable text"
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
            if label in {"Docker prune", "Docker image prune --all"} and re.search(
                r"(?:^|\s)--help(?:\s|$)", variant, re.IGNORECASE
            ):
                continue
            if label == "recursive forced Remove-Item" and re.search(
                r"(?:^|\s)-(?:whatif|wi)(?:\s|$)", variant, re.IGNORECASE
            ):
                continue
            return label
    return None


def _is_verification_command(command: str) -> bool:
    return any(
        _VERIFY_PATTERN.search(variant)
        for variant in _command_detection_variants(command)
    )


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


def _guardrail_config() -> Dict[str, Any]:
    try:
        from hermes_cli.config import load_config

        config = load_config()
    except Exception:
        return {}
    section = config.get("guardrail", {}) if isinstance(config, dict) else {}
    return section if isinstance(section, dict) else {}


def _recording_config() -> Dict[str, Any]:
    try:
        from hermes_cli.config import load_config

        config = load_config()
    except Exception:
        return {}
    section = config.get("recording", {}) if isinstance(config, dict) else {}
    return section if isinstance(section, dict) else {}


def _recording_root() -> Path:
    from hermes_constants import get_hermes_home

    return get_hermes_home() / "session-recordings"


def _recording_redactor(value: Dict[str, Any]) -> Dict[str, Any]:
    """Redact recursively and raise if the mandatory redactor is unavailable."""
    from agent.redact import redact_sensitive_text

    def visit(item: Any, key: str = "") -> Any:
        if key and _SENSITIVE_RECORDING_KEY.search(key):
            return "[REDACTED]"
        if isinstance(item, dict):
            return {str(k): visit(v, str(k)) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [visit(entry) for entry in item]
        if isinstance(item, str):
            return redact_sensitive_text(item, force=True)
        if item is None or isinstance(item, (bool, int, float)):
            return item
        return redact_sensitive_text(str(item), force=True)

    redacted = visit(value)
    if not isinstance(redacted, dict):
        raise TypeError("recording redactor must return a mapping")
    return redacted


def _recorder():
    from agent.session_recording import RecordingConfig, SessionRecorder

    return SessionRecorder(
        RecordingConfig.from_mapping(_recording_config()),
        _recording_root(),
        redactor=_recording_redactor,
    )


def _append_recording(
    session_id: str,
    event_type: str,
    payload: Dict[str, Any],
    *,
    hash_fields: Iterable[str] = (),
    hash_only_fields: Iterable[str] = (),
) -> bool:
    try:
        return _recorder().append(
            session_id,
            event_type,
            payload,
            hash_fields=hash_fields,
            hash_only_fields=hash_only_fields,
        )
    except Exception:
        # Recording is an audit aid, never a reason to break the runtime. The
        # recorder itself fails closed and writes nothing on redaction errors.
        return False


def _record_tool_decision(
    tool_name: str,
    args: Dict[str, Any],
    session_id: str,
    metadata: Dict[str, Any],
    decision: Optional[Dict[str, str]],
) -> Optional[Dict[str, str]]:
    # The final verdict is emitted centrally by post_tool_authorization after
    # any human approval round-trip. Keeping pre_tool_call side-effect free
    # prevents a requested approval from being recorded as if it were granted.
    return decision


def on_post_tool_authorization(
    tool_name: str = "",
    args: Any = None,
    session_id: str = "",
    verdict: str = "automatic",
    approval_path: str = "runtime",
    turn_id: str = "",
    tool_call_id: str = "",
    **_: Any,
) -> None:
    from agent.session_recording import sha256_json

    safe_args = args if isinstance(args, dict) else {}
    try:
        taint_snapshot = taint_status(session_id)
    except Exception:
        taint_snapshot = {"active": True, "status": "tracking_unavailable"}
    _append_recording(
        session_id,
        "tool_call",
        {
            "turn": _turn_by_session.get(_session_key(session_id), 0),
            "turn_id": turn_id,
            "tool_call_id": tool_call_id,
            "tool": tool_name or "unknown",
            "args_sha256": sha256_json(safe_args),
            "args_redacted": safe_args,
            "approval": {
                "verdict": verdict or "automatic",
                "path": approval_path or "runtime",
            },
            "taint": taint_snapshot,
        },
    )


def _taint_settings() -> tuple[int, frozenset[str], str]:
    config = _guardrail_config()
    raw_window = config.get("taint_window_turns", 3)
    if isinstance(raw_window, bool) or not isinstance(raw_window, int):
        window = 3
    else:
        window = max(0, min(raw_window, 100))

    raw_sources = config.get("taint_sources", sorted(_TAINT_SOURCES))
    if not isinstance(raw_sources, (list, tuple, set)):
        raw_sources = sorted(_TAINT_SOURCES)
    sources = frozenset(
        str(source).strip().lower()
        for source in raw_sources
        if str(source).strip().lower() in _TAINT_SOURCES
    )
    escalation = str(config.get("taint_escalation", "approve")).strip().lower()
    if escalation not in {"approve", "block", "off"}:
        escalation = "approve"
    return window, sources, escalation


def _strict_redact(value: Any) -> str:
    try:
        from agent.redact import redact_sensitive_text

        redacted = redact_sensitive_text(str(value or ""), force=True)
        return str(redacted)[:240] or "[empty]"
    except Exception:
        return "[detail unavailable: redactor failed]"


def _detail_from_args(args: Dict[str, Any]) -> str:
    for key in ("url", "uri", "path", "file", "file_path", "query", "server", "name"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return _strict_redact(value.strip())
    return "[source detail not supplied]"


def _read_path(args: Dict[str, Any]) -> Optional[Path]:
    for key in ("path", "file", "file_path", "source"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return Path(value.strip()).expanduser()
    return None


def _taint_source_for(tool_name: str, args: Dict[str, Any]) -> Optional[str]:
    normalized = str(tool_name or "").strip().lower()
    if normalized in _WEB_TOOLS or "browser" in normalized or "preview" in normalized:
        return "web"
    if normalized in _MEMORY_TOOLS or normalized.endswith("memory_search"):
        return "memory"
    if normalized in _INSTALLED_SKILL_TOOLS:
        return "installed-skill"
    if normalized in _EXTERNAL_FILE_TOOLS:
        return "external-file"

    candidate = _read_path(args)
    is_read = normalized in {"read_file", "file_read"} or normalized.endswith("_read")
    if candidate is not None and is_read and _outside_workspace(candidate)[0]:
        return "external-file"

    # Standard MCP adapter names include either ``mcp__server__tool`` or an
    # explicit server identifier. Local OmniRoute policy/diagnostic tools are
    # not external content merely because they cross the MCP transport.
    if normalized.startswith("mcp__") and "omniroute" not in normalized:
        return "mcp-external"
    return None


def _is_privileged_operation(tool_name: str, args: Dict[str, Any]) -> bool:
    normalized = str(tool_name or "").strip().lower()
    executable = _command_text(args)
    if normalized in {"terminal", "execute_code"}:
        return bool(executable) and not _is_verification_command(executable)
    if normalized in _PRIVILEGED_TOOLS or normalized.startswith("ssh"):
        return True
    if "remote" in normalized and any(
        token in normalized for token in ("connect", "exec", "write")
    ):
        return True
    if _NETWORK_COMMAND_PATTERN.search(executable) or _REMOTE_COMMAND_PATTERN.search(
        executable
    ):
        return True
    if normalized in _WRITE_TOOLS:
        return any(
            _outside_workspace(path)[0] for path in _candidate_paths(normalized, args)
        )
    if normalized in {"read_file", "file_read"}:
        candidate = _read_path(args)
        return candidate is not None and bool(
            _SENSITIVE_PATH_PATTERN.search(str(candidate))
        )
    return False


def _active_taint(session_id: str) -> Optional[tuple[TaintMark, int]]:
    window, sources, escalation = _taint_settings()
    if escalation == "off" or not sources:
        return None
    key = _session_key(session_id)
    current_turn = _turn_by_session.get(key, 0)
    marks = _taint_by_session.setdefault(key, deque())
    while marks and current_turn - marks[0].turn > window:
        marks.popleft()
    for mark in reversed(marks):
        turns_ago = max(0, current_turn - mark.turn)
        if mark.source in sources and turns_ago <= window:
            return mark, turns_ago
    return None


def _taint_escalation_decision(
    tool_name: str, session_id: str
) -> Optional[Dict[str, str]]:
    with _state_lock:
        active = _active_taint(session_id)
    if active is None:
        return None
    mark, turns_ago = active
    _window, _sources, escalation = _taint_settings()
    source = mark.source
    action = "block" if escalation == "block" else "approve"
    decision = {
        "action": action,
        "message": (
            f"Esta operação foi proposta {turns_ago} turno(s) após a leitura de "
            f"conteúdo externo ({source}: {mark.detail}). Confirme que é intenção sua."
        ),
    }
    if action == "approve":
        decision["rule_key"] = (
            f"dz23-guardrail:tainted:{tool_name or 'unknown'}:{source}"
        )
    return decision


def taint_status(session_id: str = "") -> Dict[str, Any]:
    """Return a redacted snapshot suitable for a trusted UI status surface."""
    with _state_lock:
        active = _active_taint(session_id)
        if active is None:
            return {"active": False, "source": None, "detail": None, "turns_ago": None}
        mark, turns_ago = active
        return {
            "active": True,
            "source": mark.source,
            "detail": mark.detail,
            "turns_ago": turns_ago,
        }


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
        "taint": [],
        "verification": [],
        "screenshots": [],
    }


def _report_state(session_id: str) -> Dict[str, Any]:
    return _report_state_by_session.setdefault(
        _session_key(session_id), _new_report_state()
    )


def _report_root() -> Path:
    from hermes_constants import get_hermes_home

    return get_hermes_home() / "task-reports"


def _taint_status_path(session_id: str) -> Path:
    from hermes_constants import get_hermes_home

    digest = hashlib.sha256(_session_key(session_id).encode("utf-8")).hexdigest()
    return get_hermes_home() / "runtime" / "guardrail-taint" / f"{digest}.json"


def _remove_taint_status_file(session_id: str) -> None:
    try:
        _taint_status_path(session_id).unlink(missing_ok=True)
    except OSError:
        return


def _sync_taint_status_file(session_id: str) -> None:
    active = _active_taint(session_id)
    if active is None:
        _remove_taint_status_file(session_id)
        return
    mark, turns_ago = active
    destination = _taint_status_path(session_id)
    temporary = destination.with_suffix(".tmp")
    payload = {
        "active": True,
        "source": mark.source,
        "detail": mark.detail,
        "turns_ago": turns_ago,
        "at": mark.at,
    }
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        if os.name != "nt":
            temporary.chmod(0o600)
        temporary.replace(destination)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _redact(value: str) -> str:
    try:
        from agent.redact import redact_sensitive_text

        return redact_sensitive_text(value, force=True)
    except Exception:
        raise RuntimeError("mandatory report redactor is unavailable")


def _result_mapping(result: Any) -> Dict[str, Any]:
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _reported_screenshot_path(tool_name: str, result: Any) -> Optional[Path]:
    normalized = str(tool_name or "").lower()
    if not any(
        token in normalized for token in ("screenshot", "playwright", "preview")
    ):
        return None
    payload = _result_mapping(result)
    for key in ("screenshot_path", "path", "file", "file_path"):
        raw = payload.get(key)
        if not isinstance(raw, str) or not raw.strip():
            continue
        candidate = Path(raw).expanduser().resolve(strict=False)
        if candidate.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        try:
            if candidate.is_file() and candidate.stat().st_size > 0:
                return candidate
        except OSError:
            continue
    return None


def _copy_visual_evidence(session_id: str, screenshots: Iterable[Any]) -> list[str]:
    safe_session = (
        re.sub(r"[^A-Za-z0-9_.-]+", "-", _session_key(session_id)).strip("-")[:64]
        or "session"
    )
    copied: list[str] = []
    destination_dir = _report_root() / "assets" / safe_session
    for raw in screenshots:
        source = Path(str(raw)).expanduser().resolve(strict=False)
        try:
            if not source.is_file() or source.stat().st_size <= 0:
                continue
            destination_dir.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256(str(source).encode("utf-8")).hexdigest()[:10]
            destination = destination_dir / f"{digest}-{source.name}"
            shutil.copy2(source, destination)
            try:
                destination.chmod(0o600)
            except OSError:
                pass
            copied.append(f"assets/{safe_session}/{destination.name}")
        except OSError:
            continue
    return copied


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
    verification = list(state.get("verification", []))
    verification_lines = [
        (
            f"- `{row.get('command') or '[command unavailable]'}` — "
            f"exit_code={row.get('exit_code')}, duration_ms={row.get('duration_ms', 0)}"
        )
        for row in verification
    ] or ["- No verification command with a real exit code was recorded."]
    taint_lines = [
        (
            f"- source={mark.get('source') or 'unknown'}, turn={mark.get('turn', 0)}, "
            f"at={mark.get('at') or 'unknown'}, detail={mark.get('detail') or '[redacted]'}"
        )
        for mark in state.get("taint", [])
        if isinstance(mark, dict)
    ] or ["- No external-content taint was recorded."]
    screenshot_links = _copy_visual_evidence(session_id, state.get("screenshots", []))
    visual_lines: list[str] = []
    if screenshot_links:
        visual_lines = [
            "",
            "## Visual evidence",
            "",
            *[f"![Preview evidence]({path})" for path in screenshot_links],
        ]

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
        "## Evidence",
        "",
        "### Verification commands",
        "",
        *verification_lines,
        "",
        "### External-content provenance",
        "",
        *taint_lines,
        *visual_lines,
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
        key = _session_key(session_id)
        _report_state_by_session[key] = _new_report_state()
        _taint_by_session[key] = deque()
        _turn_by_session[key] = 0
        _remove_taint_status_file(session_id)
    try:
        _recorder().prune()
    except Exception:
        pass


def on_pre_api_request(
    session_id: str = "",
    turn_id: str = "",
    api_call_count: Any = None,
    provider: str = "",
    model: str = "",
    user_message: Any = None,
    **_: Any,
) -> None:
    if api_call_count != 1:
        return
    _append_recording(
        session_id,
        "turn_start",
        {
            "turn_id": turn_id,
            "provider": provider,
            "model": model,
            "user_message": str(user_message or ""),
        },
        hash_fields=("user_message",),
    )


def on_pre_tool_call(
    tool_name: str = "", args: Any = None, session_id: str = "", **metadata: Any
) -> Optional[Dict[str, str]]:
    safe_args = args if isinstance(args, dict) else {}
    executable = _command_text(safe_args)

    if _mutates_user_spend_ceiling(tool_name, safe_args):
        return _record_tool_decision(
            tool_name,
            safe_args,
            session_id,
            metadata,
            {
                "action": "block",
                "message": (
                    "O teto local de gastos pertence ao usuário e só pode ser "
                    "alterado pela interface de configurações."
                ),
            },
        )

    label = _destructive_match(executable) if executable else None
    if label:
        return _record_tool_decision(
            tool_name,
            safe_args,
            session_id,
            metadata,
            {
                "action": "block",
                "message": f"DZ23 Guardrail blocked a destructive operation matching {label}.",
            },
        )

    if _is_privileged_operation(tool_name, safe_args):
        try:
            taint_decision = _taint_escalation_decision(tool_name, session_id)
        except Exception:
            # This plugin is a security boundary: uncertainty about the
            # provenance state escalates instead of silently behaving as if
            # no external content had entered the session.
            return _record_tool_decision(
                tool_name,
                safe_args,
                session_id,
                metadata,
                {
                    "action": "approve",
                    "message": (
                        "Não foi possível validar a proveniência do contexto desta operação. "
                        "Confirme explicitamente que é sua intenção executá-la."
                    ),
                    "rule_key": f"dz23-guardrail:tainted:{tool_name or 'unknown'}:tracking-failure",
                },
            )
        if taint_decision is not None:
            return _record_tool_decision(
                tool_name, safe_args, session_id, metadata, taint_decision
            )

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
            return _record_tool_decision(
                tool_name,
                safe_args,
                session_id,
                metadata,
                {
                    "action": "approve",
                    "message": f"Writing outside the active workspace requires explicit approval: {outside}",
                    "rule_key": f"outside-workspace:file:{path_scope}",
                },
            )

    return _record_tool_decision(tool_name, safe_args, session_id, metadata, None)


def on_post_tool_call(
    tool_name: str = "",
    args: Any = None,
    result: Any = None,
    status: Any = None,
    session_id: str = "",
    duration_ms: Any = 0,
    **metadata: Any,
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
        elif tool_name in {"terminal", "execute_code"} and _is_verification_command(
            executable
        ):
            exit_code = _verification_exit_code(result, status)
            _verified_by_session[key] = exit_code == 0
            if exit_code is not None:
                try:
                    redacted_command = _redact(executable)
                except Exception:
                    redacted_command = None
                if redacted_command is not None:
                    report["verification"].append({
                        "command": redacted_command,
                        "exit_code": exit_code,
                        "duration_ms": int(duration_ms)
                        if isinstance(duration_ms, (int, float))
                        and not isinstance(duration_ms, bool)
                        else 0,
                    })

        screenshot = _reported_screenshot_path(tool_name, result)
        if screenshot is not None and _is_success(result, status):
            report["screenshots"].append(str(screenshot))

        if _is_success(result, status):
            source = _taint_source_for(tool_name, safe_args)
            _window, configured_sources, _escalation = _taint_settings()
            if source is not None and source in configured_sources:
                mark = TaintMark(
                    source=source,
                    detail=_detail_from_args(safe_args),
                    tool=tool_name or "unknown",
                    turn=_turn_by_session.get(key, 0),
                    at=datetime.now(timezone.utc).isoformat(),
                )
                _taint_by_session.setdefault(key, deque()).append(mark)
                report["taint"].append(asdict(mark))
                _sync_taint_status_file(session_id)
    exit_code = _verification_exit_code(result, status)
    _append_recording(
        session_id,
        "tool_result",
        {
            "turn_id": metadata.get("turn_id") or "",
            "tool_call_id": metadata.get("tool_call_id") or "",
            "tool": tool_name or "unknown",
            "status": status,
            "exit_code": exit_code,
            "duration_ms": int(duration_ms)
            if isinstance(duration_ms, (int, float))
            and not isinstance(duration_ms, bool)
            else 0,
            "result": result,
        },
        hash_only_fields=("result",),
    )


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
    api_call_count: Any = None,
    turn_id: str = "",
    **_: Any,
) -> None:
    usage_dict = usage if isinstance(usage, dict) else {}
    identity = f"{provider or 'unknown'}/{model or 'unknown'}"
    with _state_lock:
        key = _session_key(session_id)
        if isinstance(api_call_count, int) and not isinstance(api_call_count, bool):
            if api_call_count == 1:
                # The first model response follows a fresh user message. It
                # establishes a new user intent and clears prior-turn taint
                # before any proposed tool call is executed.
                _taint_by_session[key] = deque()
            _turn_by_session[key] = max(0, api_call_count)
            _sync_taint_status_file(session_id)
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
    _append_recording(
        session_id,
        "api_request",
        {
            "turn_id": turn_id,
            "provider": provider or "unknown",
            "model": model or "unknown",
            "usage": usage_dict,
            "cost_usd": float(cost_usd) if isinstance(cost_usd, (int, float)) else None,
            "api_call_count": api_call_count,
        },
    )


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
    outcome = (
        "failed"
        if failed
        else "interrupted"
        if interrupted
        else "completed"
        if completed
        else "incomplete"
    )
    _append_recording(
        session_id,
        "turn_end",
        {"outcome": outcome, "completed": completed, "failed": failed},
    )
    key = _session_key(session_id)
    with _state_lock:
        state = _report_state_by_session.pop(key, None)
        _verified_by_session.pop(key, None)
        _taint_by_session.pop(key, None)
        _turn_by_session.pop(key, None)
        _remove_taint_status_file(session_id)
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
    ctx.register_hook("pre_api_request", on_pre_api_request)
    ctx.register_hook("pre_tool_call", on_pre_tool_call)
    ctx.register_hook("post_tool_authorization", on_post_tool_authorization)
    ctx.register_hook("post_tool_call", on_post_tool_call)
    ctx.register_hook("pre_verify", on_pre_verify)
    ctx.register_hook("post_api_request", on_post_api_request)
    ctx.register_hook("subagent_stop", on_subagent_stop)
    ctx.register_hook("on_session_end", on_session_end)
