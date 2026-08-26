"""Provider adapter contract + connection safety (§7/§9/§13/§30/§33).

Defines the ProviderAdapter surface (validate_config/health_check/list_models/
chat/capabilities/quota_status/pricing_metadata — not all required), a simple
connection-state vocabulary with user-friendly messages, API-key format
validation, local auto-detect URLs, and a HARD rule: secrets never reach the
renderer/logs/repo. Pure/contract module; real network probes are injected
(runtime = WAITING_FOR_HUMAN).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol


class ConnectionStatus(str, Enum):
    CONNECTED = "CONNECTED"
    INVALID_KEY = "INVALID_KEY"
    RATE_LIMITED = "RATE_LIMITED"
    NO_QUOTA = "NO_QUOTA"
    NETWORK_ERROR = "NETWORK_ERROR"
    PROVIDER_DOWN = "PROVIDER_DOWN"
    CONFIG_ERROR = "CONFIG_ERROR"
    UNKNOWN = "UNKNOWN"


_USER_MESSAGE = {
    ConnectionStatus.CONNECTED: "Connected.",
    ConnectionStatus.INVALID_KEY: "The API key looks invalid — double-check it.",
    ConnectionStatus.RATE_LIMITED: "Rate limited right now — try again shortly.",
    ConnectionStatus.NO_QUOTA: "This provider's free quota appears used up.",
    ConnectionStatus.NETWORK_ERROR: "Couldn't reach the provider — check your connection.",
    ConnectionStatus.PROVIDER_DOWN: "The provider seems to be down.",
    ConnectionStatus.CONFIG_ERROR: "Configuration problem — check the base URL/model.",
    ConnectionStatus.UNKNOWN: "Status unknown.",
}


def user_message(status: ConnectionStatus) -> str:
    return _USER_MESSAGE[status]


# API-key format hints per provider (prefix / shape). Local providers need none.
_KEY_PATTERNS: dict[str, re.Pattern[str]] = {
    "openai": re.compile(r"^sk-[A-Za-z0-9_\-]{20,}$"),
    "anthropic": re.compile(r"^sk-ant-[A-Za-z0-9_\-]{20,}$"),
    "gemini": re.compile(r"^AIza[A-Za-z0-9_\-]{20,}$"),
    "openrouter": re.compile(r"^sk-or-[A-Za-z0-9_\-]{20,}$"),
    "groq": re.compile(r"^gsk_[A-Za-z0-9]{20,}$"),
    "deepseek": re.compile(r"^sk-[A-Za-z0-9]{20,}$"),
}
_NO_KEY_PROVIDERS = frozenset({"ollama", "lmstudio", "vllm", "llamacpp"})


def validate_key_format(provider_id: str, key: str) -> bool:
    """Cheap client-side format check before any network call (§7)."""
    if provider_id in _NO_KEY_PROVIDERS:
        return True                      # local: no key needed
    pat = _KEY_PATTERNS.get(provider_id)
    if pat is not None:
        return bool(pat.match(key or ""))
    return bool(key and len(key.strip()) >= 16)   # generic non-empty


# Default local endpoints for auto-detect (§13).
_LOCAL_HEALTH = {
    "ollama": "http://127.0.0.1:11434/api/tags",
    "lmstudio": "http://127.0.0.1:1234/v1/models",
    "vllm": "http://127.0.0.1:8000/v1/models",
    "llamacpp": "http://127.0.0.1:8080/v1/models",
}


def local_health_url(provider_id: str) -> str | None:
    return _LOCAL_HEALTH.get(provider_id)


# ---- secret safety (§30) ------------------------------------------------ #

_SECRET_KEYS = ("key", "token", "secret", "password", "authorization", "credential")


@dataclass(frozen=True)
class ProviderConfig:
    """Provider config WITHOUT the secret value. The key lives only in OS-backed
    secure storage; here we keep a reference/flag, never the raw key."""

    provider_id: str
    api_base: str = ""
    model: str = ""
    has_key: bool = False
    key_ref: str | None = None          # opaque handle into secure storage
    # NOTE: there is deliberately no `api_key` field.


def sanitize_for_renderer(config: Mapping[str, object]) -> dict[str, object]:
    """Strip any secret-bearing fields before a config reaches the renderer/logs."""
    out: dict[str, object] = {}
    for k, v in config.items():
        low = k.lower()
        if any(marker in low for marker in _SECRET_KEYS):
            out[k] = "[stored securely]"
        else:
            out[k] = v
    return out


class ProviderAdapter(Protocol):
    """Contract — not every provider implements every method."""

    provider_id: str

    def validate_config(self, config: ProviderConfig) -> ConnectionStatus: ...
    def health_check(self, config: ProviderConfig) -> ConnectionStatus: ...
    def list_models(self, config: ProviderConfig) -> list[str]: ...
    def capabilities(self) -> frozenset: ...
    def quota_status(self, config: ProviderConfig) -> str: ...   # may return "UNKNOWN"
    def pricing_metadata(self) -> Mapping[str, object]: ...      # may be empty


__all__ = [
    "ConnectionStatus", "user_message", "validate_key_format", "local_health_url",
    "ProviderConfig", "sanitize_for_renderer", "ProviderAdapter",
]
