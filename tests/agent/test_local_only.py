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


# ── Context-security guarantee (Workspace U1 §8): LOCAL_ONLY nunca vira cloud ──
# A UI mostra o tri-state (LOCAL_ONLY / CLOUD_ALLOWED), mas o enforcement é aqui,
# no chokepoint de rota. Estes testes provam a garantia dura: em local-only,
# NENHUM candidato remoto é autorizado — nem por fallback quando o provider
# local falha, nem por um provider "local" apontado para uma URL remota.


def test_local_provider_pointed_at_remote_url_is_blocked() -> None:
    """Um provider com nome 'local' (ollama) mas base_url remota NÃO é local.
    Sem isso, bastaria renomear o provider para furar a fronteira."""
    policy = LocalOnlyPolicy(LocalOnlyConfig(enabled=True))

    decision = policy.authorize_route(provider="ollama", base_url="https://remoto.example/v1")

    assert decision.allowed is False
    assert decision.message.startswith("BLOCKED: local-only mode")


def test_local_only_never_authorizes_a_remote_fallback_candidate() -> None:
    """O cenário do §8: o provider local falha e a cadeia de fallback tenta um
    remoto. O enforcement roda por rota final, então CADA candidato remoto é
    negado — não há cloud mesmo quando o local cai."""
    policy = LocalOnlyPolicy(LocalOnlyConfig(enabled=True))

    # cadeia realista: local (loopback) → remotos de fallback
    fallback_chain = [
        ("ollama", "http://127.0.0.1:11434/v1"),   # o local que "falhou"
        ("openai", "https://api.openai.com/v1"),    # fallback remoto
        ("anthropic", "https://api.anthropic.com"), # outro fallback remoto
        ("groq", ""),                                # remoto sem base_url configurada
    ]
    decisions = {name: policy.authorize_route(provider=name, base_url=url) for name, url in fallback_chain}

    assert decisions["ollama"].allowed is True  # loopback ok
    # todo o resto — qualquer coisa que sairia do dispositivo — é negado
    for name in ("openai", "anthropic", "groq"):
        assert decisions[name].allowed is False, name
        assert decisions[name].message.startswith("BLOCKED: local-only mode")


def test_unconfigured_remote_provider_is_blocked() -> None:
    """Provider remoto sem base_url (rota indefinida) falha fechado — não vira
    uma chamada silenciosa a um default de cloud."""
    policy = LocalOnlyPolicy(LocalOnlyConfig(enabled=True))

    assert policy.authorize_route(provider="openai", base_url="").allowed is False


def test_local_only_config_reads_security_mapping() -> None:
    """A config vem do bloco de segurança (mesmo campo que a UI reflete)."""
    assert LocalOnlyConfig.from_mapping({"local_only": True}).enabled is True
    assert LocalOnlyConfig.from_mapping({"local_only": "on"}).enabled is True
    assert LocalOnlyConfig.from_mapping({"local_only": False}).enabled is False
    assert LocalOnlyConfig.from_mapping({}).enabled is False
    assert LocalOnlyConfig.from_mapping(None).enabled is False
