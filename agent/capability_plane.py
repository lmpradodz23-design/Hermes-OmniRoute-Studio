"""Unified policy plane for native and MCP memory, skills and plugins.

This module does not replace either implementation. It classifies both tool
surfaces, applies one provider/approval policy, and resolves cross-provider
name collisions deterministically before the existing authorization pipeline
continues. The existing pre/post tool hooks remain the audit and taint spine.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from hermes_constants import get_hermes_home, hermes_home_key

logger = logging.getLogger(__name__)

CAPABILITIES = ("memory", "skills", "plugins")
PROVIDERS = ("native", "mcp")
_MUTATING_MEMORY = {"add", "clear", "delete", "forget", "remove", "replace", "store", "write"}
_MUTATING_SKILLS = {
    "create",
    "delete",
    "edit",
    "execute",
    "install",
    "patch",
    "remove_file",
    "uninstall",
    "write_file",
}
_MUTATING_PLUGINS = {"activate", "configure", "deactivate", "install", "uninstall", "update"}
_instances: dict[str, "CapabilityPlane"] = {}
_instances_lock = threading.Lock()


def _normalized_tool_name(tool_name: str) -> str:
    return str(tool_name or "").strip().lower().replace("-", "_")


def _classification(tool_name: str, args: Mapping[str, Any]) -> tuple[str, str, str] | None:
    normalized = _normalized_tool_name(tool_name)
    provider = (
        "mcp"
        if normalized.startswith(("mcp__", "github_skills_"))
        or "omniroute_" in normalized
        else "native"
    )
    if "memory" in normalized:
        capability = "memory"
        action = str(args.get("action") or "").lower()
        if not action:
            action = next((token for token in _MUTATING_MEMORY if token in normalized), "search")
        return capability, provider, action
    if "skill" in normalized:
        capability = "skills"
        action = str(args.get("action") or "").lower()
        if not action:
            action = next((token for token in _MUTATING_SKILLS if token in normalized), "list")
        return capability, provider, action
    if "plugin" in normalized:
        capability = "plugins"
        action = str(args.get("action") or "").lower()
        if not action:
            action = next((token for token in _MUTATING_PLUGINS if token in normalized), "list")
        # Agent-visible plugin_* tools are currently supplied by OmniRoute.
        if normalized.startswith("plugin_"):
            provider = "mcp"
        return capability, provider, action
    return None


class CapabilityPlane:
    """Profile-scoped policy and deterministic provider registry."""

    def __init__(self, *, home: Path | None = None) -> None:
        self.home = Path(home or get_hermes_home())
        self._registry: dict[str, dict[str, set[str]]] = {
            capability: {provider: set() for provider in PROVIDERS}
            for capability in CAPABILITIES
        }
        self._reported_conflicts: set[tuple[str, str]] = set()
        self._lock = threading.RLock()

    def _config(self) -> dict[str, Any]:
        try:
            from hermes_cli.config import load_config_readonly

            raw = (load_config_readonly() or {}).get("capability_plane", {})
            return raw if isinstance(raw, dict) else {}
        except Exception:
            logger.exception("Capability plane config failed; using secure defaults")
            return {}

    @staticmethod
    def _bool_setting(value: Any, default: bool = True) -> bool:
        if isinstance(value, dict):
            value = value.get("enabled", default)
        return value if isinstance(value, bool) else default

    def _provider_enabled(self, capability: str, provider: str, config: Mapping[str, Any]) -> bool:
        providers = config.get("providers", {})
        if not isinstance(providers, dict):
            return True
        capability_config = providers.get(capability, {})
        if not isinstance(capability_config, dict):
            return True
        return self._bool_setting(capability_config.get(provider), True)

    def _audit(self, event: str, **payload: Any) -> None:
        destination = self.home / "runtime" / "capabilities" / "audit.jsonl"
        record = {
            "at": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **payload,
        }
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                with destination.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        except OSError:
            logger.exception("Capability audit write failed")

    def _native_skill_names(self) -> set[str]:
        root = self.home / "skills"
        if not root.exists():
            return set()
        names: set[str] = set()
        for manifest in root.rglob("SKILL.md"):
            try:
                relative = manifest.relative_to(root)
            except ValueError:
                continue
            if any(part.startswith(".") or part in {"node_modules", "__pycache__"} for part in relative.parts):
                continue
            names.add(manifest.parent.name.lower())
            try:
                for line in manifest.read_text(encoding="utf-8").splitlines()[1:30]:
                    if line.strip() == "---":
                        break
                    if line.lower().startswith("name:"):
                        declared = line.split(":", 1)[1].strip().strip("'\"").lower()
                        if declared:
                            names.add(declared)
                        break
            except OSError:
                continue
        return names

    def register_items(self, capability: str, provider: str, names: Iterable[str]) -> list[dict[str, str]]:
        if capability not in CAPABILITIES or provider not in PROVIDERS:
            raise ValueError(f"unknown capability provider: {capability}/{provider}")
        normalized = {str(name).strip().lower() for name in names if str(name).strip()}
        conflicts: list[dict[str, str]] = []
        with self._lock:
            self._registry[capability][provider].update(normalized)
            other = "mcp" if provider == "native" else "native"
            for name in sorted(normalized & self._registry[capability][other]):
                winner = "native"
                conflict = {"capability": capability, "id": name, "winner": winner}
                conflicts.append(conflict)
                key = (capability, name)
                if key not in self._reported_conflicts:
                    self._reported_conflicts.add(key)
                    logger.warning(
                        "Capability name conflict for %s/%s: native and MCP both provide it; %s wins",
                        capability,
                        name,
                        winner,
                    )
                    self._audit("provider_conflict", **conflict)
        return conflicts

    def evaluate_tool(self, tool_name: str, args: Mapping[str, Any] | None) -> dict[str, str] | None:
        safe_args = args if isinstance(args, Mapping) else {}
        classified = _classification(tool_name, safe_args)
        if classified is None:
            return None
        capability, provider, action = classified
        config = self._config()
        if config.get("enabled", True) is False:
            return None
        if not self._provider_enabled(capability, provider, config):
            message = f"BLOCKED: capability provider {capability}/{provider} is disabled by user configuration."
            self._audit(
                "provider_block",
                capability=capability,
                provider=provider,
                action=action,
                tool=_normalized_tool_name(tool_name),
            )
            return {"action": "block", "message": message, "_plugin_id": "capability-plane"}

        if capability == "skills" and provider == "mcp" and action == "execute":
            requested = str(
                safe_args.get("name")
                or safe_args.get("skill")
                or safe_args.get("skill_name")
                or safe_args.get("id")
                or ""
            ).strip().lower()
            if requested:
                self.register_items("skills", "native", self._native_skill_names())
                conflicts = self.register_items("skills", "mcp", [requested])
                if conflicts:
                    return {
                        "action": "block",
                        "message": (
                            f"BLOCKED: skill name conflict for '{requested}'; "
                            "the deterministic provider is native. Use the native skill surface."
                        ),
                        "_plugin_id": "capability-plane",
                    }

        mutations = {
            "memory": _MUTATING_MEMORY,
            "skills": _MUTATING_SKILLS,
            "plugins": _MUTATING_PLUGINS,
        }
        if action in mutations[capability] and config.get("mutations_require_approval", True) is not False:
            self._audit(
                "approval_required",
                capability=capability,
                provider=provider,
                action=action,
                tool=_normalized_tool_name(tool_name),
            )
            return {
                "action": "approve",
                "message": (
                    f"A {provider} provider wants to mutate {capability} "
                    f"({action}). Confirm this capability change."
                ),
                "rule_key": f"capability:{capability}:write",
                "_plugin_id": "capability-plane",
            }
        return None

    def describe(self) -> dict[str, Any]:
        config = self._config()
        self.register_items("skills", "native", self._native_skill_names())
        with self._lock:
            providers = {
                capability: {
                    provider: {
                        "enabled": self._provider_enabled(capability, provider, config),
                        "items": sorted(self._registry[capability][provider]),
                    }
                    for provider in PROVIDERS
                }
                for capability in CAPABILITIES
            }
            conflicts = [
                {"capability": capability, "id": name, "winner": "native"}
                for capability, name in sorted(self._reported_conflicts)
            ]
        return {
            "enabled": config.get("enabled", True) is not False,
            "mutations_require_approval": config.get("mutations_require_approval", True) is not False,
            "providers": providers,
            "conflicts": conflicts,
        }


def get_capability_plane(*, home: Path | None = None) -> CapabilityPlane:
    resolved = Path(home or get_hermes_home())
    key = hermes_home_key(resolved)
    with _instances_lock:
        plane = _instances.get(key)
        if plane is None:
            plane = CapabilityPlane(home=resolved)
            _instances[key] = plane
        return plane
