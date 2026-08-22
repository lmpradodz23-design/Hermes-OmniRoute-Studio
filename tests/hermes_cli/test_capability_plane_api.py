from __future__ import annotations

import asyncio
from contextlib import nullcontext


def test_capability_provider_api_persists_one_provider(monkeypatch):
    from hermes_cli.web_models import CapabilityProviderToggle
    from hermes_cli.web_routers import capabilities

    config = {
        "capability_plane": {
            "providers": {
                "memory": {"native": True, "mcp": True},
                "skills": {"native": True, "mcp": True},
                "plugins": {"native": True, "mcp": True},
            }
        }
    }
    saved = []
    monkeypatch.setattr(capabilities, "_CONFIG_MUTATION_LOCK", nullcontext())
    monkeypatch.setattr(capabilities, "_profile_scope", lambda _profile: nullcontext())
    monkeypatch.setattr(capabilities, "load_config", lambda: config)
    monkeypatch.setattr(capabilities, "save_config", lambda value: saved.append(value))
    monkeypatch.setattr(
        "agent.capability_plane.CapabilityPlane.describe",
        lambda self: {"providers": config["capability_plane"]["providers"]},
    )

    result = asyncio.run(
        capabilities.update_capability_provider(
            "skills",
            "mcp",
            CapabilityProviderToggle(enabled=False),
        )
    )

    assert saved
    assert config["capability_plane"]["providers"]["skills"]["mcp"] is False
    assert result["providers"]["skills"]["mcp"] is False
