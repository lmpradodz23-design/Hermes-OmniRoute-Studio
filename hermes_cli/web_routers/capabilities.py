"""Unified memory/skills/plugins capability-plane dashboard API."""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException

from hermes_cli.web_deps import LateState, late
from hermes_cli.web_models import CapabilityProviderToggle

router = APIRouter()
_profile_scope = late("_profile_scope")
load_config = late("load_config")
save_config = late("save_config")
_CONFIG_MUTATION_LOCK = LateState("_CONFIG_MUTATION_LOCK")
_CAPABILITIES = {"memory", "skills", "plugins"}
_PROVIDERS = {"native", "mcp"}


@router.get("/api/capability-plane")
async def get_capability_plane(profile: Optional[str] = None):
    def _read():
        with _profile_scope(profile):
            from agent.capability_plane import get_capability_plane as _plane

            return _plane().describe()

    return await asyncio.to_thread(_read)


@router.put("/api/capability-plane/providers/{capability}/{provider}")
async def update_capability_provider(
    capability: str,
    provider: str,
    body: CapabilityProviderToggle,
    profile: Optional[str] = None,
):
    if capability not in _CAPABILITIES or provider not in _PROVIDERS:
        raise HTTPException(status_code=400, detail="Unknown capability provider")

    def _write():
        with _CONFIG_MUTATION_LOCK, _profile_scope(profile):
            config = load_config()
            plane = config.setdefault("capability_plane", {})
            providers = plane.setdefault("providers", {})
            capability_config = providers.setdefault(capability, {})
            capability_config[provider] = body.enabled
            save_config(config)
            from agent.capability_plane import get_capability_plane as _plane

            return _plane().describe()

    return await asyncio.to_thread(_write)
