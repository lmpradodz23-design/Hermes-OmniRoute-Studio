# Arquitetura — Hermes OmniRoute Studio

Visão de alto nível das camadas e das **fronteiras de confiança**. Detalhes por
subsistema estão em `docs/` (RAPTOR, OpenWA/WhatsApp) e `audit/`.

## Fluxo principal

```
Workspace U1 (Electron/React, apps/desktop)
    │  IPC validado (allowlist) — o renderer nunca chama primitiva perigosa direto
    ▼
Agents / Goals / Memory
    ▼
OmniRoute (roteamento multi-modelo; política LOCAL_ONLY enforçada no core)
    ▼
MCP / Tools  (capability-gated no ponto de execução)
    ▼
Providers (Anthropic / OpenAI / Gemini / local … conforme política)
```

## Security Research (RAPTOR) — desacoplado

```
Hermes → SecurityEngine → RaptorAdapter (argv-only, shell=False, tetos, timeout)
                              ▼
                       RAPTOR runtime EXTERNO (sandbox Linux/macOS)
                              ▼
                    SARIF / findings  [UNTRUSTED OUTPUT]
                              ▼
        parser validado → Finding normalizado → fronteira de projeto
```

Modos que executam conteúdo não confiável exigem sandbox real → no Windows nativo
retornam `BLOCKED_BY_PLATFORM_SECURITY`. Nenhum código do RAPTOR é copiado no core.

## WhatsApp (OpenWA) — desacoplado

```
Hermes → WhatsAppProvider → OpenWA Adapter (Easy API, 127.0.0.1, apiKey obrigatória)
                              ▼
                     OpenWA runtime EXTERNO (@open-wa/wa-automate)
```

Toda mensagem recebida é `UNTRUSTED_INPUT` — nunca vira instrução nem concede
capability automaticamente. O agente propõe; a `OutboundPolicy` decide o envio.
QR/tokens/sessões nunca no git nem em log.

## Fronteiras de confiança (resumo)

- **Renderer → main (Electron):** só IPC allowlisted.
- **Core → egress:** `LOCAL_ONLY` enforçado em `agent/local_only.py` (fora de
  prompt/plugin/MCP) — em local-only, nenhuma rota/tool de cloud é autorizada.
- **Auto-update:** um checkout fork/divergente/sujo NUNCA é auto-atualizado para
  `main` (fork-guard em `apps/desktop/electron/update-policy.ts`); update que
  falha entra em backoff persistido (não reloopa o boot).
- **Dados de terceiros (SARIF, mensagens, saída de LLM):** dado, nunca instrução.

## Development checkout vs Installed product

- **Development checkout:** este repositório (git). NÃO é uma instalação
  atualizável automaticamente para `main` — o fork-guard impede isso de propósito.
- **Installed product:** o instalador Windows (objetivo público final) entrega
  Hermes OmniRoute Studio sem exigir Git/WSL/npm/Python manuais do usuário final.

Ver também: `docs/RAPTOR_INTEGRATION_ARCHITECTURE.md`,
`docs/OPENWA_INTEGRATION_ARCHITECTURE.md`, `audit/P0_STARTUP_REGRESSION_DIAGNOSIS.md`.
