# OPENWA_INTEGRATION_CHECKPOINT

```
current_wave=TODAS as waves de lógica pura concluídas (MCP, cron, guardrails, agent bridge, memória, cliente Easy API); só restam waves device+phone
completed=WAVE 0 (audit), 1 (license+v4/v5), 2 (arquitetura/contrato), 4 (sessão/QR states), 5 (send/receive/events domain), 8 (security domain), MCP (9023888), agent bridge (630fb4e), memória (e994edd), cliente Easy API (8f5f891)
files_changed=whatsapp_provider/{__init__,session,events,sending,validation,easyapi,provider,process_manager,capabilities,mcp_tools,outbound_policy,cron_policy,agent_bridge,memory,client}.py + tests/whatsapp_provider/* + docs + .gitignore
tests_run=whatsapp_provider + security_research 219/219 passed; canários (capability gate, no-false-success, privileged confirmation, outbound gate, dedup, redação de memória, fail-closed, key-só-no-header, endpoint allowlist) todos mordem; smokes rodados no PC real (desktop-prado)
remaining=SÓ device+phone: WhatsApp Studio UI, auth HTTP real, runtime real+QR+send/receive (gate do telefone), build Windows/NSIS/installed E2E, contagem matriz MCP no gateway — ver audit/OPENWA_DEVICE_EXECUTOR_PROMPTS.md
blockers=OPENWA-LIC-1 (bundling), WAITING_FOR_HUMAN_QR_SCAN (device+phone), device-required (UI/packaging)
next_exact_action=no PC: rodar o runbook abaixo (npx @open-wa/wa-automate@4.76.0), escanear QR, e então validar send/receive contra número controlado
```

## Versão/commit auditados

```
OPENWA_COMMIT=56102e628c19a18216ac1d2eb7b31858fa1b2560
OPENWA_VERSION=5.0.0-alpha (branch master) — BASELINE OPERACIONAL ESCOLHIDA: 4.76.0 (npm latest, estável)
OPENWA_BRANCH=master
OPENWA_TRACK=V4_STABLE (v5 em compatibility track via interface WhatsAppProvider)
LICENSE=H-DNH (Hippocratic + Do No Harm) — runtime externo, sem bundling
```

## Feito neste turno (evidência)

- Wave 0-2: OpenWA clonado e auditado por subagente independente (runtime
  A/B/C, drivers, sessão/QR, eventos, envio, MCP, v4/v5, testes, Windows).
- Licença resolvida: H-DNH força runtime externo → `docs/OPENWA_LICENSE_AUDIT.md`.
- Domínio testável (`whatsapp_provider/`): máquina de estados de sessão, eventos
  normalizados + dedup por message.id, envio (SENT só com id real), rate-limit,
  anti-loop, validação (IDs/texto/mídia/browser args), config do runtime externo
  (loopback + apiKey obrigatória + redação de log). **51 testes, 2 canários.**
- Docs: OPENWA_LICENSE_AUDIT, OPENWA_INTEGRATION_ARCHITECTURE, WHATSAPP_PROVIDER.
- `.gitignore`: diretórios de sessão fora do source control.

## Correção metodológica (2º turno) e preflight

- Licença: `docs/OPENWA_LICENSE_AUDIT.md` reescrito para separar FACT /
  LICENSE_TEXT / PACKAGE_METADATA / ARCHITECTURAL_DECISION / LEGAL_QUESTION. A
  propagação sobre toda a distribuição é `LEGAL_REVIEW_REQUIRED`, não afirmada
  como fato. A decisão de runtime externo é robusta a qualquer parecer.
  `LICENSE_RISK=CONFIRMED`, `WHOLE_DISTRIBUTION_LICENSE_PROPAGATION=REQUIRES_LEGAL_REVIEW`.
- Preflight no PC (device_bash / WSL): **Node v22.23.2, npm 10.9.8, npx ok**.
  Nenhum artefato de sessão rastreado no git. Prerequisitos de runtime presentes.
- Implementado neste turno: `provider.py` (contrato abstrato + contract tests),
  `process_manager.py` (ownership, restart backoff, crash≠logout). Total do
  módulo agora: **62 testes**.

## Wave MCP — superfície `whatsapp.*` (commit `9023888`)

Implementada e testada no cloud (lógica pura, sem device):

| módulo | papel |
|---|---|
| `whatsapp_provider/capabilities.py` | `WhatsAppCapability` (READ/MANAGE/SEND/SEND_MEDIA) + `WhatsAppGrants` (default só READ). Capacidade concedida explicitamente, nunca por mensagem recebida. |
| `whatsapp_provider/mcp_tools.py` | `WhatsAppMcpDispatcher`, allowlist de 9 tools `whatsapp.*`. Ordem única no ponto de execução: allowlist → capacidade → schema → estado → executa. API crua do OpenWA nunca exposta. |
| `whatsapp_provider/outbound_policy.py` | barreira mensagem-recebida (UNTRUSTED) → ação. Ação privilegiada (shell/fs/ssh/cron/bulk_send/data_export) exige human-in-the-loop. |
| `whatsapp_provider/cron_policy.py` | `CronGuard`: só jobs allowlisted, idempotência + teto diário. |

Garantias provadas por teste (com **canary** confirmando que cada defesa é real —
teste falha quando a defesa é removida, passa quando restaurada):

- `SEND` sem grant → `DENIED` (não envia).
- send em sessão não conectada → `QR_REQUIRED`/`NOT_AUTHENTICATED`, **nunca** `OK`
  (sem sucesso falso).
- tool fora da allowlist → `DENIED`.
- ação privilegiada pedida por mensagem recebida → `NEEDS_CONFIRMATION`.
- cadeia de prompt injection: mensagem de contato conhecido continua
  `untrusted=True`, não escala capability, não sai da allowlist.

Regressão no cloud: `tests/whatsapp_provider/ + tests/security_research/` =
**186 passed**. Nenhum arquivo do core tocado.

Ainda device/phone-required (próximas waves): agents wiring end-to-end real,
WhatsApp Studio UI, auth local Hermes↔OpenWA, build Windows/NSIS/installed E2E,
contagem da matriz MCP no gateway, e o envio/recebimento real (gate do QR).

## Waves de lógica pura concluídas após MCP (bridge, memória, cliente)

Todas testadas no cloud, canariadas (teste falha quando a defesa é removida) e
com smoke rodado no PC real (desktop-prado):

| wave | commit | módulo | garantia central provada |
|---|---|---|---|
| Agent bridge | `630fb4e` | `agent_bridge.py` | mensagem recebida é DADO NÃO CONFIÁVEL; o agente injetado é o único interpretador e NÃO envia — todo candidato passa pela OutboundPolicy. Agente comprometido por prompt injection ainda é barrado. Dedup impede resposta dupla. |
| Memória | `e994edd` | `memory.py` | fronteira única de persistência: nunca token/apiKey/cookie/QR(dataURL)/bytes de mídia; texto redigido+limitado; `assert_no_secrets` falha fechado. |
| Cliente Easy API | `8f5f891` | `client.py` | auth local Hermes↔OpenWA sem rede aqui (transporte injetado); key só no header, nunca URL/body/log/repr; path só da allowlist de endpoints. |

Sequência da missão cumprida no cloud: **MCP → Agents → Cron → Guardrails →
Memória → (auth, forma testável)**. O que sobra é genuinamente device+phone.

## Runbook para o PC (Wave 4/5/14 — device+phone)

```powershell
# 1. runtime externo (v4 estável) — o usuário aceita a H-DNH direto com o upstream
$env:WA_API_KEY = "<gerar-uma-chave-forte>"
npx --yes @open-wa/wa-automate@4.76.0 --session hermes-test --port 8080 --host 127.0.0.1 --api-key $env:WA_API_KEY
# 2. escanear o QR mostrado no terminal/arquivo com o telefone  ← WAITING_FOR_HUMAN_QR_SCAN
# 3. validar do Hermes: GET http://127.0.0.1:8080/getConnectionState (header X-API-Key)
# 4. enviar para número CONTROLADO: POST /sendText {"args":{"to":"<num>@c.us","content":"teste hermes"}}
# 5. responder desse número e confirmar o evento onMessage no Hermes
```

## Blockers

```
BLOCKER-ID=OPENWA-QR-1
TYPE=WAITING_FOR_HUMAN_QR_SCAN
COMPONENT=autenticação da sessão WhatsApp
REASON=exige o telefone do operador escaneando o QR — ação física, não automatizável
UNBLOCK=operador escaneia o QR; a validação continua automaticamente depois
```
```
BLOCKER-ID=OPENWA-LIC-1
TYPE=BLOCKED_BY_LICENSE_CONSTRAINT
COMPONENT=@open-wa/wa-automate (H-DNH)
REASON=propagação de licença; runtime externo instalado pelo usuário (adotado)
```
```
BLOCKER-ID=OPENWA-DEVICE-1
TYPE=BLOCKED_BY_PLATFORM_SECURITY
COMPONENT=WhatsApp Studio UI + packaging NSIS + installed E2E + runtime real
REASON=exigem a máquina Windows e conta/telefone; não reproduzíveis no cloud
```

## Não regrediu

RAPTOR (`b4a3e20`) e o fix-loop das auditorias (`7e51f88`) intactos. OpenWA é
aditivo — pacote novo `whatsapp_provider/`, nenhum arquivo do core tocado além
do `.gitignore`.
