from agent.local_only import LocalOnlyConfig, LocalOnlyPolicy


def test_remote_model_route_is_blocked() -> None:
    policy = LocalOnlyPolicy(LocalOnlyConfig(enabled=True))

    decision = policy.authorize_route(
        provider="openai",
        base_url="https://api.openai.com/v1",
    )

    assert decision.allowed is False
    assert decision.message.startswith("BLOCKED: local-only mode")


def test_loopback_model_routes_are_allowed() -> None:
    policy = LocalOnlyPolicy(LocalOnlyConfig(enabled=True))

    for provider, base_url in (
        ("ollama", "http://127.0.0.1:11434/v1"),
        ("lmstudio", "http://localhost:1234/v1"),
        ("custom", "http://[::1]:8080/v1"),
    ):
        assert policy.authorize_route(provider=provider, base_url=base_url).allowed


def test_remote_egress_tools_are_blocked_but_local_preview_is_allowed() -> None:
    policy = LocalOnlyPolicy(LocalOnlyConfig(enabled=True))

    for tool_name in (
        "web_search",
        "web_extract",
        "omniroute_web_fetch",
        "oneproxy_fetch",
        "notion_search",
        "obsidian_remote_read",
        "browser_exec",
    ):
        decision = policy.authorize_tool(tool_name, {})
        assert decision.allowed is False, tool_name
        assert decision.message.startswith("BLOCKED: local-only mode")

    assert policy.authorize_tool("read_preview", {}).allowed
    assert policy.authorize_tool("read_file", {"path": "README.md"}).allowed


def test_disabled_policy_is_a_noop() -> None:
    policy = LocalOnlyPolicy(LocalOnlyConfig(enabled=False))

    assert policy.authorize_route(provider="openai", base_url="https://api.openai.com/v1").allowed
    assert policy.authorize_tool("web_search", {}).allowed
