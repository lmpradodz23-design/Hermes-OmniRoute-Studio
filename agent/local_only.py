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

