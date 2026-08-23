"""Core-enforced local-only routing and tool-egress policy.

This policy is intentionally outside prompts, plugins, and MCP. The model
cannot override it, and a plugin failure cannot turn it off. It protects the
two core egress chokepoints Hermes controls: model requests and tool dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from typing import Any, Mapping
from urllib.parse import urlparse


_LOCAL_PROVIDERS = frozenset({"ollama", "lmstudio", "lm-studio", "llama.cpp", "llamacpp"})
_LOCAL_HOSTS = frozenset({"localhost", "host.docker.internal", "host.containers.internal", "gateway.docker.internal"})
_ALWAYS_REMOTE_TOOL_MARKERS = (
    "web_search",
    "web_extract",
    "web_fetch",
    "oneproxy_fetch",
    "browser_exec",
    "notion",
    "composio",
    # Cloud media generation (fal.ai etc.) — no loopback path; content leaves the
    # machine. Registered tool names: image_generate / video_generate.
    "image_generate",
    "video_generate",
)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _is_loopback_url(value: str) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    try:
        parsed = urlparse(raw if "://" in raw else f"http://{raw}")
        host = (parsed.hostname or "").strip().lower().rstrip(".")
    except (TypeError, ValueError):
        return False
    if host in _LOCAL_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class LocalOnlyConfig:
    enabled: bool = False

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "LocalOnlyConfig":
        mapping = value if isinstance(value, Mapping) else {}
        return cls(enabled=_as_bool(mapping.get("local_only", False)))


@dataclass(frozen=True)
class LocalOnlyDecision:
    allowed: bool
    message: str = ""


class LocalOnlyViolation(RuntimeError):
    """Raised when a route would leave the local machine under local-only mode.

    Raised at the AUXILIARY egress chokepoint (auxiliary_client._create_openai_client
    and the Gemini/native builders) so that compression, title, vision, MoA,
    one-shot, plugin-LLM and cloud-fallback calls can never quietly send content
    to a remote provider — the same boundary conversation_loop already enforces
    for the main route. Fail-closed: any non-loopback route is denied.
    """


# Cache of the raw persisted local_only read, keyed by config path → (mtime,
# size, value). Avoids a YAML parse on every off-reading (the common case) while
# staying correct: any edit to config.yaml changes mtime/size and re-reads.
_PERSISTED_LOCAL_ONLY_CACHE: dict = {}


def _compute_persisted_local_only(path) -> Any:
    try:
        import yaml

        raw = path.read_text(encoding="utf-8")
    except Exception:
        return "unknown"  # present but unreadable → indeterminate
    try:
        parsed = yaml.safe_load(raw)
    except Exception:
        return "unknown"  # present but unparseable (corrupt YAML) → indeterminate
    if parsed is None:
        return False  # empty file → legitimate default-off
    if not isinstance(parsed, dict):
        return "unknown"  # malformed top-level structure → indeterminate
    security = parsed.get("security", {})
    if not isinstance(security, Mapping):
        return False
    return _as_bool(security.get("local_only", False))


def _read_persisted_local_only() -> Any:
    """Read security.local_only DIRECTLY from the on-disk config file, bypassing
    the merge/overlay/last-known-good machinery of load_config().

    Returns:
      * True / False — the persisted value (or explicit absence → False).
      * "fresh"      — no config file exists yet (legitimate default-off install).
      * "unknown"    — a config file EXISTS but cannot be read/parsed (corrupt,
                       truncated, unreadable): the security state is indeterminate.

    This is the authority used to distinguish a genuine "off" from a corrupt file
    that silently dropped local_only, so a critical privacy preference never fails
    open just because the persisted state is damaged.
    """
    try:
        from hermes_cli.config import get_config_path

        path = get_config_path()
    except Exception:
        # Cannot even resolve where config lives → cannot assert a file exists →
        # treat as fresh (never brick a broken/fresh install into fail-closed).
        return "fresh"
    try:
        st = path.stat()
    except FileNotFoundError:
        return "fresh"
    except Exception:
        return "unknown"  # a path that exists but cannot be stat'd → indeterminate

    # Nanosecond mtime (not whole-second) so a same-second in-place repair/edit
    # of the config is not served a stale cached verdict.
    mtime = getattr(st, "st_mtime_ns", st.st_mtime)
    key = str(path)
    cached = _PERSISTED_LOCAL_ONLY_CACHE.get(key)
    if cached is not None and cached[0] == mtime and cached[1] == st.st_size:
        return cached[2]

    value = _compute_persisted_local_only(path)
    _PERSISTED_LOCAL_ONLY_CACHE[key] = (mtime, st.st_size, value)
    return value


def config_local_only_enabled() -> bool:
    """Read the PERSISTED security.local_only. For enforcement points that run
    OUTSIDE a per-turn context (memory plugins, background/CLI jobs) and cannot
    consult the auxiliary ContextVar. Single source of truth for that fallback —
    callers must not re-implement config reading.

    FAIL-CLOSED on unknown state: local_only is a critical privacy preference, so
    it must NOT silently disable itself when the persisted config is corrupt,
    truncated, or unreadable, nor when a merge/overlay path drops the user's
    value. A genuine fresh install (no config file) still defaults OFF so it is
    not broken. Precedence:
      1. If the normal effective read says ON → ON.
      2. Else cross-check the raw persisted file: a raw ON, or an UNKNOWN (present
         but unreadable/corrupt) state → deny egress (True).
      3. Otherwise (genuine off, or fresh install) → OFF.
    """
    effective = None
    try:
        from hermes_cli.config import load_config

        effective = LocalOnlyConfig.from_mapping((load_config() or {}).get("security", {})).enabled
    except Exception:
        effective = None

    if effective:
        return True

    # effective is False (parsed off, or overlay-dropped) or None (load failed):
    # consult the persisted file directly so corruption / a dropped value cannot
    # silently turn the boundary off.
    try:
        raw = _read_persisted_local_only()
    except Exception:
        # The cross-check itself failed unexpectedly. Mirror the historical
        # fail-open ONLY when we also could not read effectively; if we had an
        # effective value (False), honor it.
        return False if effective is False else False

    if raw is True:
        return True
    if raw == "unknown":
        return True  # UNKNOWN_SECURITY_CONFIG → deny remote egress (fail closed)
    # raw is False or "fresh" → genuine off / fresh install.
    return bool(effective) if effective is not None else False


def egress_denial_reason(*, provider: str, base_url: str) -> str:
    """Denial message if this model route would leave the machine, else ''.

    Shares the EXACT loopback rule with LocalOnlyPolicy.authorize_route so the
    auxiliary boundary can never diverge from the main one. Callers invoke this
    only when local-only is active for the current context.
    """
    normalized_provider = str(provider or "").strip().lower()
    if _is_loopback_url(base_url) or (normalized_provider in _LOCAL_PROVIDERS and not str(base_url or "").strip()):
        return ""
    target = str(base_url or provider or "unconfigured remote provider")
    return f"BLOCKED: local-only mode permits only loopback model providers; auxiliary route '{target}' was denied"


class LocalOnlyPolicy:
    """Immutable per-agent privacy boundary for provider and tool egress."""

    def __init__(self, config: LocalOnlyConfig) -> None:
        self.config = config

    def authorize_route(self, *, provider: str, base_url: str) -> LocalOnlyDecision:
        if not self.config.enabled:
            return LocalOnlyDecision(True)

        normalized_provider = str(provider or "").strip().lower()
        if _is_loopback_url(base_url) or (normalized_provider in _LOCAL_PROVIDERS and not str(base_url or "").strip()):
            return LocalOnlyDecision(True)

        target = str(base_url or provider or "unconfigured remote provider")
        return LocalOnlyDecision(
            False,
            f"BLOCKED: local-only mode permits only loopback model providers; route '{target}' was denied",
        )

    def authorize_tool(self, tool_name: str, args: Mapping[str, Any] | None) -> LocalOnlyDecision:
        if not self.config.enabled:
            return LocalOnlyDecision(True)

        normalized = str(tool_name or "").strip().lower().replace("-", "_")
        blocked = any(marker in normalized for marker in _ALWAYS_REMOTE_TOOL_MARKERS)
        blocked = blocked or ("obsidian" in normalized and "remote" in normalized)
        blocked = blocked or (normalized.startswith("browser_") and normalized not in {"browser_status"})

        if not blocked:
            return LocalOnlyDecision(True)

        return LocalOnlyDecision(
            False,
            f"BLOCKED: local-only mode denied network-capable tool '{tool_name}'",
        )

