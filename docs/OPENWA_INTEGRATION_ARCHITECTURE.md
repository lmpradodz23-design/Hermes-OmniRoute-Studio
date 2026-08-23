# OpenWA — Arquitetura de Integração

Alvo: `@open-wa/wa-automate`. Decisões baseadas na auditoria de código do Wave 0
e na auditoria de licença (`OPENWA_LICENSE_AUDIT.md`).

## Decisão de acoplamento

```
Hermes → WhatsAppService → WhatsAppProvider (interface) → OpenWAProvider → OpenWA runtime (EXTERNO)
```

O core do Hermes conhece só a interface `WhatsAppProvider`. O `OpenWAProvider`
é o único ponto que conhece o OpenWA. Trocar de provider, atualizar ou desligar
o OpenWA é mexer só no adapter.

## Decisão v4 vs v5

| | v4.76.0 | v5.0.0-alpha |
|---|---|---|
| npm dist-tag | **`latest` (estável)** | `alpha` |
| arquitetura | pacote único | monorepo (Effect, Hono, Zod) |
| envio de arquivo/reação/PTT | funciona | **17 métodos `unsupported` no runtime embarcado** |
| listeners migrados | — | **0/30** (`client_migration_doc.md`) |
| mídia migrada | — | **0/40** |
| recomendação do próprio README | — | "keep production on 4.76.0" |

```
V4_STABILITY=estável (latest no npm, base do produto por anos)
V5_MATURITY=alpha — envio de arquivo/reação/PTT e listeners não backados no runtime
V5_FEATURE_ADVANTAGE=monorepo, runtimes edge/bun, tipagem Effect/Zod (futuro)
V5_BREAKING_RISK=alto — Easy API reorganizada, webhook do CLI só emite warning
```

**Decisão: v4.76.0 como baseline operacional** (`easyapi.py` lança
`@open-wa/wa-automate@4.76.0`), com a interface `WhatsAppProvider` permitindo
trocar para v5 num compatibility track quando amadurecer. O Hermes nunca depende
cegamente da v5-alpha.

## Decisão de runtime

Três estratégias avaliadas:

| | A — Easy API (HTTP) | B — SocketClient | C — Embedded |
|---|---|---|---|
| isolamento de crash | **alto** (Chromium em processo separado) | alto (consome A) | baixo (Chromium no processo Electron) |
| a auditoria mostrou | servidor Hono, porta 8080, bind `localhost`, apiKey **opcional** | é a lib-consumidora de A (SSE+fetch) | `createClient`, roda Chromium no processo |

**Decisão: A (Easy API) como processo externo**, consumido por HTTP em
`127.0.0.1`. Motivos convergentes: contenção de crash (um travamento do
Chromium/WhatsApp Web não derruba o Electron), e a licença H-DNH que já obriga
runtime externo. **Nunca embedded no renderer.**

Dois endurecimentos sobre o default do upstream (a auditoria achou frouxo):
- **bind sempre 127.0.0.1** (o default é `localhost`, mas garantimos loopback e
  recusamos 0.0.0.0);
- **apiKey obrigatória** (no upstream é opcional; aqui um processo local hostil
  não é confiável — §52). A key vai por env `WA_API_KEY`, nunca no argv (não
  vaza em `ps`).

## Trust boundaries

```
Electron Renderer
      │  (IPC allowlisted, validado, autorizado — nunca método OpenWA arbitrário)
      ▼
Hermes WhatsApp Service (Python)
      ▼
OpenWAProvider (adapter)
      ▼  HTTP 127.0.0.1 + apiKey
OpenWA Easy API (processo externo)
      ▼
Browser Driver (Puppeteer) → WhatsApp Web
```

Toda mensagem recebida é `UNTRUSTED_INPUT` (`events.py`, `untrusted=True`):
nunca vira instrução nem concede capability. A defesa não é o prompt — é o gate
no ponto de execução (validação, allowlist de tools, capability policy).

## Componentes implementados (testáveis no cloud, 51 testes)

| módulo | papel |
|---|---|
| `whatsapp_provider/session.py` | máquina de estados da sessão — `CONNECTED` sem conexão fingida |
| `whatsapp_provider/events.py` | normalização OpenWA→Hermes + dedup por `message.id` |
| `whatsapp_provider/sending.py` | envio (`SENT` só com id real) + rate-limit + anti-loop |
| `whatsapp_provider/validation.py` | IDs/texto/mídia (path traversal) + allowlist de browser args |
| `whatsapp_provider/easyapi.py` | config do runtime externo: loopback + apiKey obrigatória + redação de log |

## O que exige o dispositivo Windows + telefone (não simulável)

- **Iniciar o OpenWA real + browser + QR** → `WAITING_FOR_HUMAN_QR_SCAN`: exige
  a máquina Windows, o Chromium e o telefone do operador escaneando o QR.
- **Envio/recebimento E2E real** → conta WhatsApp controlada pelo operador.
- **WhatsApp Studio UI (Electron), packaging NSIS, smoke do app instalado** →
  build/execução no Windows.

Entregue como runbook executável (`audit/OPENWA_INTEGRATION_CHECKPOINT.md`), não
como concluído. O adapter e o domínio estão prontos e testados; o E2E é
device+phone-required por natureza.
