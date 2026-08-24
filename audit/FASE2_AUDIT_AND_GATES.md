# Hermes OmniRoute Studio — Fase 2: Auditoria independente + Matriz de Gates

Data: 2026-08-23. Baseline auditado: `develop @ 275dad4` (clone limpo do GitHub OSS,
`git clone --depth 1`, 10.783 arquivos). Testes reproduzidos em container Linux limpo
(node v22, `npm ci` + `npm rebuild esbuild`), NÃO no PC do usuário.

**Regra de honestidade (§51):** `SOURCE_PASS != RUNTIME_PASS`. Nada aqui foi validado
no app Windows instalado. Onde não pude executar em runtime, a classificação é
`SOURCE_ONLY_NOT_RUNTIME_VALIDATED`, nunca `PASS`.

Método: 4 auditorias independentes e adversariais (não confirmatórias) sobre o clone
autoritativo do GitHub, tracing UI → IPC/API → domínio → runtime, + execução real das
suítes de teste que rodam no container.

---

## 0. Discrepância de ambiente registrada (BLOCKED_BY_EXTERNAL_DEPENDENCY)

- O prompt aponta a árvore autoritativa Windows como
  `C:\Users\you\Documents\Codex\Hermes-OmniRoute@GitHub`, mas essa pasta **não está
  conectada** ao ambiente. Só `C:\Users\you\Documents\Codex\Hermes-OmniRoute` está.
- Ação: auditei o **clone do GitHub** (fonte de verdade) e entrego correções na pasta
  conectada `Hermes-OmniRoute` (cujo HEAD pós-publicação = `275dad4` = GitHub). Se você
  quiser que eu trabalhe na `@GitHub`, conecte-a no app.

---

## 1. P0 — Updater / Startup (PRIORIDADE ABSOLUTA, §5)

### 1.1 O P0 nomeado (fork com origin não-oficial) está FECHADO — com evidência
`resolveUpdatePolicy` força `MANUAL_REQUIRED` para fork/dirty/ahead/origin-não-oficial;
`decideUpdateGate` roda no TOPO de `applyUpdates` **antes** de qualquer kill de backend,
probe de venv ou marker/handoff (`main.ts:3613`), e em não-PROCEED inicia o backend e
retorna sem tocar no runtime. Nenhum caller automático passa `force=true`.

**Evidência de execução (container limpo):**
- `update-policy/backoff/decision/venv-blocker` → **56/56 testes passam**.
- Suíte electron completa → **1630 passed / 9 skipped** (baseline), **1633 / 9** após as
  correções abaixo. `tsc -p tsconfig.electron.json` limpo.

### 1.2 Fail-open encontrados e CORRIGIDOS nesta entrega (§5 pedia caça a fail-open)
A auditoria adversarial achou 3 caminhos onde "estado desconhecido" virava permissão de
auto-update num checkout de **origin oficial** (o fork com origin não-oficial já estava
protegido, mas um checkout custom no origin oficial, sob anomalia de leitura git, não).

| # | Defeito | Local | Correção (causa raiz) | Estado |
|---|---|---|---|---|
| P1-A | `catch` do gate era **fail-open**: qualquer exceção caía no caminho destrutivo ("proceeding"), contrariando o próprio cabeçalho "Fails SAFE". | `main.ts:3669-3673` | catch agora inicia backend e **retorna skip** (`update-gate-error`); nunca cai no handoff. | **FIXED + typecheck** |
| P1-B | Branch vazio (git rev-parse falhou → `''`) **pulava** a checagem de divergência → podia virar AUTO. | `update-policy.ts:56` | branch atual/rastreado vazio → `MANUAL_REQUIRED` ("unknown != safe"). | **FIXED + teste J/K + canary** |
| P1-C | Leituras git falhas mascaradas em valores benignos (`''`/`'0'` para ahead), escondendo trabalho local. | `main.ts:3620-3626` | rastreio `readFailed`; qualquer leitura crítica falha → **skip** (`update-state-unknown`), backend inicia. `behind` continua "unknown = disponível". | **FIXED** |

**Prova das correções:** testes `update-policy` = 24 passam (incl. J/K + canary). **Canary
verificado**: removendo o guard de branch-desconhecido, 3 testes falham; restaurando, 13
passam. Suíte electron completa pós-fix: **1633 passed / 9 skipped**.

### 1.3 Fail-open residuais (NÃO corrigidos nesta passada — registrados)
- **P2 — TOCTOU cross-process**: a seção destrutiva (kill backend em `main.ts:3784`) não
  tem lock; o marker só é escrito depois (`~3910/3944`). Duas instâncias podem passar o
  check e ambas matar backends. *Correção proposta:* lock exclusivo (`wx`/O_EXCL) antes do
  primeiro passo destrutivo. Precisa de teste de concorrência → executor.
- **P2 — dois returns de falha não gravam backoff** (`main.ts:~3799` holder externo,
  `~3978` spawn-failed). *Correção:* `recordUpdateFailure`+persist nos dois.
- **P2 — arquivo de backoff corrompido** cai para `INITIAL` (sem backoff) → protege menos
  contra loop. *Correção:* em erro de parse (arquivo presente porém inválido), aplicar
  janela de backoff conservadora em vez de zero. (`update-backoff.ts:96`)
- **P3 — `.git` inacessível** faz o gate ser pulado (trata como instalação empacotada).
  Aceito por ora: bloquear "sem .git" quebraria o auto-update do instalador empacotado
  (público-alvo real). Documentado.

### 1.4 Gate P0
`P0_UPDATER_STARTUP = SOURCE_ONLY_NOT_RUNTIME_VALIDATED` (source correto e endurecido,
1633 testes verdes; **runtime Windows pendente de rebuild** — §6/§27).

---

## 2. LOCAL_ONLY (§11 — inegociável) — **FAIL: egress auxiliar não protegido**

Verificado por leitura + grep (não só um arquivo): `authorize_route` existe **apenas** em
`agent/conversation_loop.py` e `agent/local_only.py`. `agent/auxiliary_client.py` **não
tem nenhuma** referência a local_only/authorize_route.

- **O chokepoint principal (loop de conversa) É protegido** e fail-closed
  (`conversation_loop.py:2977`; `local_only.py` bloqueia rota não-loopback; provider
  "local" apontando para URL remota é bloqueado). `test_local_only.py` valida a **unidade
  da política** — mas não o wiring dos outros caminhos.
- **Gaps reais (mais graves primeiro):**
  1. `auxiliary_client.call_llm/_call_llm_impl` (compression, vision, title, MoA, oneshot,
     plugin_llm) — **segundo chokepoint de egress totalmente sem gate**. Conteúdo do
     workspace é enviado sem `authorize_route`. Em local_only, hoje só não vaza por
     coincidência (resolve para o provider loopback), não por enforcement.
  2. **Fallback automático para cloud em falha/402** (`auxiliary_client.py:~9394`,
     `_try_configured_fallback_for_unavailable_client`). É exatamente o "local falha →
     cloud" que §11 proíbe.
  3. **Visão cai para cloud** sob local_only (`resolve_vision_provider_client("auto")` →
     OpenRouter/Nous/`api.anthropic.com`) quando o modelo local não é backend de visão.
  4. `image_generate`/`video_generate` alcançam cloud (nome não bate no denylist de
     `authorize_tool`).
  5. **Egress de tool é denylist (fail-open)**, não allowlist — tool/MCP com nome
     desconhecido passa.
  6. `agent/account_usage.py` faz POST para `api.anthropic.com`/`chatgpt.com`/OpenRouter
     sem gate (metadados/credenciais; sem conteúdo de documento, severidade menor).

**Por que NÃO corrigi nesta passada (honestidade §3/§51):** o seam limpo existe (o
ContextVar `_RUNTIME_MAIN_CONTEXT` em `auxiliary_client.py:3220`), mas as chamadas
auxiliares (compression/title) rodam **automaticamente**; um erro no gate quebraria o app,
e **não consigo validar em runtime o stack de modelos neste ambiente de nuvem**. Landar
cego violaria "não quebre trabalho válido" e "não declare PASS sem executar". Entrego a
correção como spec de executor (ver `FASE2_EXECUTOR_PROMPTS.md`).

`LOCAL_ONLY = FAIL` (enforcement só no loop principal; egress auxiliar/visão/gen/fallback
não protegido). **Não** classificar como PASS.

---

## 3. Segurança / Electron (§19) — baseline forte, 2×P1 de seam

Sem P0. Hardening genuinamente bom: `contextIsolation:true, nodeIntegration:false,
sandbox:true, webSecurity:true` em todas as 10 janelas; preload é **allowlist** (~140
canais nomeados, sem `ipcRenderer` genérico); escrita de fs com contenção por realpath;
navegação travada (`setWindowOpenHandler` nega tudo); webview de Preview força
sandbox/isolation/sem-preload; CSP sem `unsafe-eval`/inline-script; logs com `redactSecrets`.

**P1 (seam) — corrigir antes de release:**
1. **Token do gateway exposto ao renderer e colocado em query string de URL**
   (`main.ts:12463` retorna `token`; `media.ts:126`, `plugins.ts:95` → `?token=`).
   Vaza para logs/history/referrer; qualquer script no renderer lê o token. *Correção:*
   mover para header `Authorization`, cunhar por-uso (como o ticket de WS), manter o token
   no main.
2. **Leitura de arquivo não é root-scoped** (`readFileText/DataUrl/ForAttach` em
   `main.ts:14142+` usam denylist, não os allowed-roots da escrita). Renderer comprometido
   lê quase todo o disco (menos o denylist). *Correção:* aplicar o mesmo
   `resolveAllowedFsIpcPath` da escrita.

**P2:** arg-injection em `git opts.base` (falta `--` end-of-options,
`git-worktree-ops.ts:311`); devTools sempre on em janelas de chat/preview.

`SECURITY = SOURCE_ONLY_NOT_RUNTIME_VALIDATED` com 2×P1 abertos (não é PASS até corrigir).

---

## 4. "Bombar o Hermes" — matriz de existência (§8)

Achado central: ~1/3 dos nomes são **de brochura** (só em `audit/*.md`), sem código nem
UI — aspiracionais, não "botões falsos". O produto real é grande e coerentemente ligado.

| Subsistema | Classificação | Evidência |
|---|---|---|
| Computer Use | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | `tools/computer_use/cua_backend.py` (175KB) → `/api/tools/computer` → `settings/computer-use-panel.tsx`; 10 testes. Precisa do cua-driver. |
| Watchdog/resume | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | `gateway/shutdown_watchdog.py`, `session_stall.py`; resume em `gateway/session.py`. |
| Self-Healing | PARTIAL | comportamento transversal (reconnect, cron wedge, state-db, worktree), cada um testado; sem engine unificada. |
| Hermes Doctor | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | CLI + `/api/ops/doctor` (`web_server.py:14149`) + UI `command-center/maintenance.tsx`. Wired ponta a ponta. |
| Safe Repair | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | `hermes_state.py:2265` (backup + ledger + lock cross-proc); `bootstrap-repair-guard.ts`. |
| Knowledge Graph | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | `plugins/memory/hindsight/` (2669L) → `agent/memory_provider.py` → `/api/memory`. |
| Skill Factory | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | `tools/skill_manager_tool.py` + `skills_hub.py` (6.5K L) → `/api/skills` → `app/skills`. |
| MCP Registry | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | `web_routers/mcp.py` (catalog/install/servers/OAuth) → `api/mcp.ts`. |
| sandbox | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | `tools/code_execution_tool.py` (allowlist 7 tools) + `tools/environments/{docker,modal,daytona,ssh,...}.py`. |
| Git worktree isolation | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | `tools/subagent_worktree.py` → `delegate_tool.py` (`worktree_isolation`, default False) → `/api/git/worktree/*`. |
| observability | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | `hermes_cli/observability/shared_metrics.py`; health monitors. |
| cost/resource governor | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | `agent/spend_ceiling.py` (hard-ceiling ANTES do request) no loop. |
| Visual QA | MISSING | sem engine; só primitivas de visão. |
| Evidence Engine | MISSING | só em scripts de skill. |
| Mission DAG | MISSING | "Mission Control" é monitor de processo, não DAG. |
| Release Factory | MISSING | só scripts `dist:*` do electron-builder. |
| Impact Analysis | MISSING | — |
| Test Intelligence | MISSING | — |
| Canary Engine | MISSING | "canary" só em comentários. |
| Model Benchmark Arena | MISSING | só harness de eval estreito. |
| Mobile Lab | MISSING | `apps/mobile` é wrapper Capacitor do `web/`. |

**Top features reais e wired:** Computer Use, Cron/agendados, Git review/worktree, MCP
catalog, Skills authoring, Hindsight memory, gateway/relay (WhatsApp), profiles/toolsets,
Ops (Doctor/Safe-repair), Spend ceiling + observability.

---

## 5. U1 — superfícies órfãs (IMPLEMENTED_NOT_INTEGRATED) — honestidade

As camadas de domínio criadas anteriormente têm **testes verdes mas 0 importers no app**
(não estão montadas em rota/pane/palette/contribution). São "testes que mentem": passam,
mas a feature é inalcançável na UI.

| Superfície | Estado | Arquivo |
|---|---|---|
| model-routing | SOURCE_ONLY (0 importers) | `src/app/model-routing/routing.ts` |
| context-panel | SOURCE_ONLY (0 importers) | `src/app/context-panel/context-model.ts` |
| security-research | SOURCE_ONLY (0 importers) | `src/app/security-research/*.ts` |
| whatsapp (state machine) | SOURCE_ONLY (0 importers) | `src/app/whatsapp/whatsapp-surface.ts` |
| goals/goal-authoring | SOURCE_ONLY (0 importers) | `src/app/goals/goal-authoring.ts` |
| memory/memory-inline | SOURCE_ONLY (0 importers) | `src/app/memory/memory-inline.ts` |
| agents/agent-authoring | SOURCE_ONLY (0 importers) | `src/app/agents/agent-authoring.ts` |

Superfícies U1 **realmente wired e funcionando** (EXISTS_AND_WORKS por tracing): shell,
sidebar, chat, composer, right panes, artifacts, files, diff, preview, command palette,
sessions, agents (overlay), memory/starmap (grafo real via `/api/learning/graph`),
terminal, settings.

**Ação recomendada (§8: completar+integrar, não paralelizar):** ou montar essas 7 camadas
em superfícies reais do U1, ou removê-las. Enquanto órfãs, **não** contam como feature
entregue. Integração é trabalho de UI que exige runtime do app → executor/próxima passada.

---

## 6. Matriz de Gates de Release (§47) — classificação honesta

Vocabulário: `PASS | FAIL | BLOCKED | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | WAITING_FOR_HUMAN`.

| Gate | Estado | Base |
|---|---|---|
| P0_UPDATER_STARTUP | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | source correto + endurecido, 1633 testes; runtime Windows pendente |
| WINDOWS_COLD_START | BLOCKED (rebuild) | não há toolchain Windows/NSIS/display neste ambiente |
| WINDOWS_RESTART | BLOCKED (rebuild) | idem |
| BACKEND_READY | BLOCKED (rebuild) | idem |
| LOCAL_ONLY | **FAIL** | egress auxiliar/visão/gen/fallback não protegido (§2) |
| OMNIROUTE | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | routing existe; provider health não validado em runtime |
| AGENTS | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | overlay wired; delegação herda política no loop principal (aux não) |
| GOALS | PARTIAL | status wired; authoring órfão |
| MEMORY | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | starmap/hindsight wired |
| MCP | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | catalog/install/OAuth wired |
| COMPUTER_USE | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | precisa cua-driver |
| PRODUCT_STUDIO | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | skill + preview; fluxo E2E não validado |
| SECURITY_RESEARCH | SOURCE_ONLY (UI órfã) | adapter existe; UI 0 importers |
| TERMINAL | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | PTY wired, shell server-side |
| FILES / ARTIFACTS / DIFF / PREVIEW | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | wired via IPC |
| SECURITY (Electron/supply-chain) | SOURCE_ONLY + 2×P1 | token-em-URL, leitura fs não-scoped |
| INSTALLER | BLOCKED (rebuild) | — |
| PT_BR | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | precisa abrir o app em pt-BR |
| ACCESSIBILITY | SOURCE_ONLY_NOT_RUNTIME_VALIDATED | precisa app instalado |
| VISUAL_QA | BLOCKED (rebuild + display) | — |
| OPENWA | WAITING_FOR_HUMAN_QR_SCAN | código pronto; falta o QR (dependência física) |

**Nenhum gate de runtime pode ir a PASS sem o rebuild Windows.** Nenhum
`SOURCE_ONLY_NOT_RUNTIME_VALIDATED` foi promovido a PASS.

---

## 7. Itens BLOCKED_BY_EXTERNAL_DEPENDENCY (fora do meu ambiente)

- **Rebuild + instalador Windows + validação de runtime do P0** (§6/§27): sem
  toolchain Windows (vite/electron/NSIS são win32-only), sem display. → executor no PC.
- **QR do WhatsApp** (§44): dependência física (celular). `WAITING_FOR_HUMAN_QR_SCAN`.
- **Sandbox Linux/macOS do RAPTOR** (§14/§43): execução real exige sandbox; no Windows
  nativo é `BLOCKED_BY_PLATFORM_SECURITY` por design.
- **Árvore `@GitHub` não conectada** (§0).

## 8. O que foi entregue nesta passada (evidência)
- Correções P0 fail-open (P1-A/B/C) no source, com teste + **canary verificado** e suíte
  electron **1633/9** verde; `tsc` electron limpo. Arquivos: `apps/desktop/electron/main.ts`,
  `update-policy.ts`, `update-policy.test.ts`.
- Esta auditoria consolidada + matriz de gates + achados de segurança.
- Specs de executor para o que exige o PC (rebuild/P0-runtime) e para o fix de LOCAL_ONLY
  (risco de regressão sem runtime) — em `FASE2_EXECUTOR_PROMPTS.md`.

## 9. O que ainda falta (explícito, §50.17)
- Validar P0 em runtime no Windows (rebuild). — **maior risco aberto.**
- Fechar LOCAL_ONLY (egress auxiliar/visão/gen/fallback). — **FAIL até lá.**
- Corrigir 2×P1 de Electron (token-em-URL; leitura fs não-scoped).
- Integrar ou remover as 7 superfícies U1 órfãs.
- P2 do updater (TOCTOU lock, backoff nos 2 returns, backoff corrompido).
- QR do WhatsApp; runtime do RAPTOR; auditoria dos 3 agentes sobre o app instalado.
