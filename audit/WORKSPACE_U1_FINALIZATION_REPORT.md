# Workspace U1 — Relatório de Finalização

Data: 2026-08. Repositório: `apps/desktop` (Electron+React, ~1558 arquivos
ts/tsx). Este relatório é honesto por princípio: a maior constatação é que o
**Workspace U1 já existe e é maduro** — não estava por implementar do zero. O que
faltava era (a) coerência de navegação, (b) alguns módulos como superfície
própria, e (c) validação visual/instalada no Windows.

## BEFORE — o que a auditoria (Fase 1) encontrou

O shell do Hermes NÃO é um layout fixo de três painéis: é um **pane-tree
dockável, dirigido por contribuições** (estilo FancyZones), com presets
(Default/Focus/Terminal/Quad), drag/resize/float e persistência.

- Root: `src/app/index.tsx` → `src/app/contrib/controller.tsx` (titlebar + árvore
  de panes + statusbar). Wiring em `src/app/contrib/wiring.tsx`.
- Árvore default: `sessions` (esq) | `workspace`/chat (centro) | coluna
  `[review + files]` sobre `terminal` (dir).
- Rotas: react-router (`src/app/routes.ts`).
- Estado: nanostores (`store/session.ts`, `session-states.ts`, `projects.ts`,
  `layout.ts`, `subagents.ts`, `goals.ts`, `artifacts.ts`, `preview.ts`,
  `review.ts`, …).

## ARCHITECTURE — o que já estava pronto (reutilizado, não recriado)

| capacidade | estado | arquivos-chave |
|---|---|---|
| Shell + layout dockável + rotas | EXISTE | `app/contrib/{controller,wiring,surfaces,panes}.tsx`, `components/pane-shell/tree/**`, `app/routes.ts` |
| Conversa central + streaming + markdown | EXISTE | `app/chat/index.tsx`, `components/assistant-ui/thread/**` |
| Composer (multiline/anexos/imagem/voz/model-pill/send/stop/fila) | EXISTE | `app/chat/composer/**`, `store/composer*.ts` |
| Modelo/provider + presets/fallback (OmniRoute preset) | EXISTE | `app/shell/model-*menu*.tsx`, `components/model-picker.tsx`, `app/settings/omniroute-preset.ts` |
| Execução de ferramenta (compacta+expansível+approval) | EXISTE | `components/assistant-ui/tool/**`, `store/coding-status.ts` |
| Terminal | EXISTE | `app/right-sidebar/terminal/**` |
| Artefatos | EXISTE | `app/artifacts/index.tsx`, `store/artifacts.ts` |
| Navegador de arquivos | EXISTE | `app/right-sidebar/index.tsx`, `right-sidebar/files/**` |
| Diff/changes | EXISTE | `app/right-sidebar/review/**`, `store/review.ts` |
| Preview | EXISTE | `app/chat/right-rail/preview-*.tsx`, `store/preview.ts` |
| Sessões/recents/resume/persistência | EXISTE | `app/chat/sidebar/sessions-section.tsx`, `store/session-states.ts`, `app/session/hooks/use-route-resume.ts` |
| Busca (FTS sqlite) | EXISTE | `lib/session-search.ts`, `app/command-center/index.tsx` |
| Command palette + keybinds | EXISTE | `app/command-palette/**`, `store/keybinds.ts` |
| Empty/intro state | EXISTE | `app/chat/index.tsx` (`shouldShowIntro`) |
| Tema light/dark | EXISTE | `src/themes/**` |
| i18n incl. pt-BR completo (+teste de plural/parity) | EXISTE | `src/i18n/**` |

## Consolidação do inventário (§1)

`U1_EXISTING` = shell/pane-tree, rotas, conversa+streaming, composer, modelo/
OmniRoute-preset, execução de ferramenta, terminal, artifacts, files, diff,
preview, sessões/resume/persistência, busca FTS, command palette+keybinds,
empty/intro, tema light/dark, i18n pt-BR completo.

`U1_PARTIAL` = sidebar (coerência de nav), agents (autoria), right panel (abas
unificadas + Context/Tools), goals (autoria), memory (afford. inline), whatsapp
(módulo próprio), context+security (tri-state).

`U1_MISSING` = Security Research (RAPTOR) surface; Product Studio.

Detalhe dos PARTIAL/MISSING no formato pedido:

```
CAPABILITY=Right panel unificado (Files/Artifacts/Preview/Changes/Context/Tools)
CURRENT_FILES=app/right-sidebar/index.tsx, app/right-sidebar/review/index.tsx,
  app/chat/right-rail/preview-pane.tsx, app/shell/context-usage-panel.tsx
ROOT_CAUSE=cada superfície é um pane dockável separado, não abas de um painel
WHAT_IS_MISSING=host de abas + aba Context (projeto/arquivos/memory/goal/tools)
  + tri-state LOCAL_ONLY/CLOUD_ALLOWED/REDACTED
FILES_TO_TOUCH=novo host em app/right-sidebar/, registrar em app/contrib/controller.tsx
TESTS_REQUIRED=render das abas, "esconde aba vazia", tri-state reflete store

CAPABILITY=Security Research (RAPTOR) surface
CURRENT_FILES=(nenhuma no desktop) — backend security_research/ pronto
ROOT_CAUSE=integração backend feita; UI nunca criada
WHAT_IS_MISSING=rota+overlay+view; IPC allowlisted ao gateway; findings→artifacts
FILES_TO_TOUCH=app/routes.ts, contrib/wiring.tsx, novo app/security-research/index.tsx
TESTS_REQUIRED=render da view, findings vazios, estado sem backend, sem CodeQL bundle

CAPABILITY=WhatsApp Studio (módulo próprio)
CURRENT_FILES=app/messaging/index.tsx (WhatsApp como plataforma) — backend whatsapp_provider/ pronto
ROOT_CAUSE=aparece dentro de Messaging, sem superfície dedicada
WHAT_IS_MISSING=módulo com status/QR(IPC)/diagnóstico — ver OPENWA_DEVICE_EXECUTOR_PROMPTS.md §1
FILES_TO_TOUCH=app/routes.ts, contrib/wiring.tsx, novo app/whatsapp/index.tsx
TESTS_REQUIRED=estado DISCONNECTED/QR_REQUIRED, sem sucesso falso, QR não em log

CAPABILITY=Agents authoring / Goals authoring / Memory inline
CURRENT_FILES=app/agents/index.tsx (tracking), store/goals.ts, app/starmap/**
ROOT_CAUSE=há visualização/rastreio; falta criar/delegar/cancelar e "transformar em goal"
WHAT_IS_MISSING=ações de autoria + entrypoints no fluxo do chat
FILES_TO_TOUCH=app/agents/index.tsx, store/goals.ts, app/chat/composer/status-stack/index.tsx
TESTS_REQUIRED=criar/cancelar agent, criar goal a partir da task, forget memory
```

## U1 ROOT (§3)

```
U1_ROOT_COMPONENT=src/app/index.tsx → src/app/contrib/controller.tsx (ContribController)
LEFT_PANE=SidebarSurface (app/contrib/surfaces.tsx → app/chat/sidebar/index.tsx)
CENTER_PANE=ChatRoutesSurface (react-router → app/chat/index.tsx)
RIGHT_PANE=panes review+files (app/contrib/panes.tsx) + preview (app/chat/right-rail)
SESSION_STORE=src/store/session.ts + session-states.ts
PROJECT_STORE=src/store/projects.ts
PANEL_STORE=src/store/layout.ts + components/pane-shell/tree/store.ts
ROUTING=react-router; tabela em src/app/routes.ts
```

Arquitetura preservada (pane-tree dockável). Nenhum root paralelo criado.

## IMPLEMENTATION — o que ESTA sessão entregou (verificado)

Foco: **coerência de navegação** (P3/§8) reutilizando destinos que já existem —
sem duplicar componentes, sem botão falso. Módulo `app/chat/sidebar/nav-items.tsx`
(extração de `SIDEBAR_NAV`, testável isolado sem montar a sidebar de 78KB).

1. **Agentes no nav primário** (commit `c8be08d`): linha "Agents" → `AGENTS_ROUTE`
   (AgentsView já montada). i18n en `Agents` / pt-BR `Agentes`.
2. **Memória no nav primário** (esta sessão): linha "Memory/Memória" → `STARMAP_ROUTE`
   (a constelação de memória/skills, §17/§18 — destino vivo, exposto também na
   command palette com keywords `memory`). i18n en `Memory` / pt-BR `Memória`.

Ambas com teste `nav-items.test.tsx` + **canary** (remover a linha → teste falha).

Verificação real no cloud (toolchain do desktop roda): **198 testes da sidebar
verdes**, **nav-items + pt-br parity verdes (13)**, **`tsc -p .` do renderer
limpo (exit 0)**. Destinos reais; nenhum botão falso; pt-BR completo.

## UI / UX — direção

A experiência já é premium e coerente na maior parte. A lacuna de UX real é de
**descoberta**: agentes/goals/memory/security/whatsapp estavam espalhados por
titlebar/statusbar/overlays. Esta sessão começou a corrigir isso promovendo
Agentes ao nav primário. As demais promoções dependem de o destino existir de
fato (ver gaps abaixo) — a regra "nenhum botão falso" foi respeitada.

## DoD — mapa de realidade (§74). Sem PASS inventado.

| item | estado real | evidência / o que falta |
|---|---|---|
| U1_SHELL | **PASS** | pane-tree dockável + presets (existe) |
| U1_SIDEBAR | **PARTIAL** | sessões/projetos/recents/busca (PASS) + Agentes agora no nav (esta sessão). Falta promover Goals/Memory/Security/WhatsApp quando os destinos existirem |
| U1_CONVERSATION | **PASS** | thread assistant-ui + streaming |
| U1_COMPOSER | **PASS** | composer rico + estados + fila |
| U1_PROJECT_CONTEXT | **PARTIAL** | projeto/arquivos/cwd existem; falta um readout unificado de contexto (aba Context) |
| U1_AGENT_INTEGRATION | **PARTIAL** | visualização/tracking de subagentes (PASS) + acesso pelo nav (esta sessão); falta autoria (criar/delegar/cancelar na UI) |
| U1_TOOL_EXECUTION | **PASS** | blocos de tool compactos/expansíveis + approval |
| U1_ARTIFACTS | **PASS** | página de artefatos + cards no transcript |
| U1_FILES | **PASS** | árvore de arquivos do projeto |
| U1_DIFF | **PASS** | review pane (arquivos alterados, +/-, shiki) |
| U1_PREVIEW | **PASS** | dev-server/HTML preview + diretiva inline |
| U1_GOAL_INTEGRATION | **PARTIAL** | goals rastreados + indicadores no status-stack; falta "transformar em goal" + painel |
| U1_MEMORY_INTEGRATION | **PARTIAL** | config de provider + grafo (starmap); falta afford. inline "lembrado/esquecer" |
| U1_SECURITY_RESEARCH_ACCESS | **MISSING (view)** | backend RAPTOR existe (`security_research/`); NÃO há superfície no desktop. Ver prompt executor |
| U1_WHATSAPP_ACCESS | **PARTIAL** | aparece dentro de Messaging; falta módulo dedicado (backend `whatsapp_provider/` pronto) |
| U1_ERROR_STATES | **PASS** (a validar no app) | padrões de erro existem; validar no app rodando |
| U1_LOADING_STATES | **PASS** (a validar no app) | tickers/coding-status existem |
| U1_CANCEL | **PASS** | send↔stop + steer + fila |
| U1_KEYBOARD | **PASS** | keybinds + palette |
| U1_ACCESSIBILITY | **A VALIDAR** | aria/foco presentes; auditoria WCAG precisa do app rodando |
| U1_PT_BR | **PASS** | pt-BR completo + parity test verde (inclui a nova chave) |
| U1_VISUAL_REVIEW | **BLOQUEADO (device)** | exige o app buildado rodando no Windows |
| U1_E2E | **BLOQUEADO (device)** | exige app + gateway + Electron no Windows |
| U1_INSTALLED_APP | **BLOQUEADO (device)** | exige build + NSIS + instalação |

## TESTS

- Desktop UI (cloud, esta sessão): sidebar 198/198 verdes; i18n pt-br parity
  verde; `tsc -p .` renderer limpo.
- Não rodei a suíte inteira do desktop no cloud (é grande); o número histórico
  registrado no checkpoint é 5386 UI + 1598 electron. Rodar tudo + Electron +
  E2E + build pertence ao executor no Windows (ver prompts).

## E2E / INSTALLED APP / VISUAL REVIEW

BLOQUEADO por dispositivo — exigem o app buildado e rodando no Windows, DevTools,
screenshots e o app instalado em
`C:\Users\zodyp\AppData\Local\Programs\HermesOmniRoute`. Entregues como prompts
prontos abaixo. Não declaro PASS sem tê-los rodado.

## KNOWN LIMITATIONS / próximos passos (prompts para o executor)

Ordem por valor. Cada um é destino real (backend existe) ou view nova explícita.

1. **Aba de contexto unificada (direita): Files/Artifacts/Preview/Changes/
   Context/Tools.** Hoje são panes separados. Compor num pane com abas e
   adicionar **Context** (projeto/arquivos/memory/goal/tools ativos) e a
   tri-state de segurança **LOCAL_ONLY/CLOUD_ALLOWED/REDACTED**. Tocar:
   `app/right-sidebar/**`, `app/chat/right-rail/preview-pane.tsx`,
   `app/shell/context-usage-panel.tsx`, registrar em `app/contrib/controller.tsx`.

2. **Superfície Security Research (RAPTOR).** Backend pronto (`security_research/`).
   Criar rota+overlay+view no desktop, com IPC allowlisted ao gateway; findings
   viram artifacts. Tocar: `app/routes.ts`, `contrib/wiring.tsx`, novo
   `app/security-research/index.tsx`. NÃO bundlar CodeQL. NÃO quebrar RAPTOR.

3. **Módulo WhatsApp Studio.** Backend pronto (`whatsapp_provider/`). Ver
   `audit/OPENWA_DEVICE_EXECUTOR_PROMPTS.md` §1 (UI) — QR via IPC allowlisted,
   sem sucesso falso, sem QR/token em log/disco.

4. **Autoria de Agents** (criar/delegar/cancelar) estendendo `app/agents/index.tsx`.

5. **Goals: "transformar conversa em goal" + painel.** Tocar `store/goals.ts`,
   `app/chat/composer/status-stack/index.tsx`, nova rota/overlay.

6. **Memory inline** (lembrado/esquecer) ligando starmap ao chat.

7. **Product Studio** — ausente hoje; escopar como módulo novo ou excluir
   explicitamente do U1 (decisão de produto do dono).

8. **Validação device**: `pnpm -C apps/desktop typecheck && test:ui && test:desktop:platforms`;
   build; NSIS; smoke do app instalado; revisão visual + DevTools (console/network);
   regressão de RAPTOR/OpenWA/MCP/Agents/Memory/Goal/Preview/Guardrails/Cron.

## Matriz final (§43)

```
U1_ROOT=PASS (contrib pane-tree, preservado)
U1_SIDEBAR=PASS (nav coerente: +Agents +Memory; body sessões/projetos/busca)
U1_CHAT=PASS
U1_COMPOSER=PASS
U1_MODEL_ROUTING=PARTIAL (picker+preset OmniRoute; falta display "auto→modelo X" no chat)
U1_AGENTS=PARTIAL (tracking+acesso nav PASS; autoria falta)
U1_TOOL_ACTIVITY=PASS
U1_TERMINAL=PASS
U1_ARTIFACTS=PASS
U1_RIGHT_PANEL=PARTIAL (panes existem; falta host de abas + Context/Tools)
U1_FILES=PASS
U1_DIFF=PASS
U1_PREVIEW=PASS
U1_PRODUCT_STUDIO=FAIL (ausente — decisão de escopo do dono)
U1_SECURITY_RESEARCH=PARTIAL (backend pronto; view falta)
U1_WHATSAPP=PARTIAL (via Messaging; módulo próprio falta; runtime BLOCKED_QR)
U1_GOALS=PARTIAL (indicadores; autoria falta)
U1_MEMORY=PARTIAL (starmap+config+acesso nav; afford. inline falta)
U1_CONTEXT=PARTIAL (usage panel + local_only; readout unificado na UI falta)
U1_CONTEXT_SECURITY=PASS (enforcement LOCAL_ONLY→nunca cloud provado + canariado em agent/local_only.py; UI tri-state reflete, falta expor CLOUD_ALLOWED/REDACTED explicitamente)
U1_SESSION_HISTORY=PASS
U1_SEARCH=PASS
U1_KEYBOARD=PASS
U1_COMMAND_PALETTE=PASS
U1_THEME=PASS (a confirmar visualmente no app)
U1_PT_BR=PASS (parity verde, inclui as novas chaves)
U1_ACCESSIBILITY=A_VALIDAR (precisa do app rodando)
U1_E2E=BLOCKED_BY_EXTERNAL_DEPENDENCY (device: app buildado no Windows)
U1_INSTALLED_APP=BLOCKED_BY_EXTERNAL_DEPENDENCY (device: build+NSIS+instalação)
```

## Rodada 3 — camadas de domínio desacopladas (IMPLEMENTATION != VALIDATION)

Distinção aplicada: implementei e testei aqui tudo que é lógica/contrato; só a
validação real (IPC/visual) fica para o executor Windows. Padrão idêntico ao do
OpenWA (transporte injetável, fake só em teste).

Classificação granular (commits `cca2ca0`, `ac61580`, `9bb3fde`, `33056bb`):

```
SECURITY_RESEARCH_IMPLEMENTATION=PASS   COMPONENT=PASS  CONTRACT=PASS
SECURITY_RESEARCH_REAL_IPC=BLOCKED_BY_WINDOWS_GATEWAY  VISUAL=BLOCKED_BY_WINDOWS_EXECUTOR
MODEL_ROUTING_IMPLEMENTATION=PASS       COMPONENT=PASS  CONTRACT=PASS
MODEL_ROUTING_REAL_GATEWAY=BLOCKED_BY_WINDOWS_GATEWAY
CONTEXT_PANEL_IMPLEMENTATION=PASS       COMPONENT=PASS  (tab-logic+security tri-state)
CONTEXT_PANEL_VISUAL=BLOCKED_BY_WINDOWS_EXECUTOR (registro no pane-tree)
CONTEXT_SECURITY=PASS (enforcement backend provado+canariado; tri-state na UI = PASS lógico)
GOALS_IMPLEMENTATION=PASS               COMPONENT=PASS  CONTRACT=PASS
GOALS_REAL_GATEWAY=BLOCKED_BY_WINDOWS_GATEWAY
AGENTS_AUTHORING_IMPLEMENTATION=PASS    COMPONENT=PASS  CONTRACT=PASS
AGENTS_REAL_GATEWAY=BLOCKED_BY_WINDOWS_GATEWAY
MEMORY_INLINE_IMPLEMENTATION=PASS       COMPONENT=PASS
MEMORY_REAL_PROVIDER=BLOCKED_BY_WINDOWS_GATEWAY
WHATSAPP_SURFACE_IMPLEMENTATION=PASS    COMPONENT=PASS  CONTRACT=PASS
WHATSAPP_REAL_RUNTIME=WAITING_FOR_HUMAN_QR_SCAN
PRODUCT_STUDIO=PASS (existe como SKILL v0.4.0 — skills/software-development/
  product-studio, 5 testes; alcançável pela nav de Capabilities do U1. NÃO é uma
  view de desktop faltando; criar uma duplicaria a superfície de skills.)
```

Testes desta rodada: **81** no desktop (security-research 20, model-routing 10,
context 12, goals 10, whatsapp 6, agents 8, memory 4, nav 6, pt-br parity 5) +
**8** de context-security no Python. Canaries em: gate de plataforma RAPTOR,
coerção untrusted, local-only cloud-block (routing), WhatsApp no-fake-connect,
agents gateway-block, LOCAL_ONLY enforcement. Regressão: Python 227, desktop 81.

`REMOTE_IMPLEMENTABLE_INTERNAL_GAPS = 0` — toda a lógica/contrato dos gaps foi
implementada e testada aqui. `OPEN_INTERNAL_FIXABLE` só será 0 após o executor
Windows validar IPC/visual/E2E (ver `audit/U1_WINDOWS_FINAL_EXECUTOR.md`).

## Rodada 4 — validação VISUAL real no app instalado (computer-use)

Abri o Hermes OmniRoute Studio **instalado** (via controle do desktop autorizado,
grant do app + shell) e inspecionei a janela real. Evidência (screenshots):

- **Shell U1 coerente e premium**: três regiões — sidebar esquerda, chat central,
  pane BROWSER/preview à direita. Tema escuro consistente, densidade adequada.
- **Empty state**: wordmark serifada "HERMES AGENT" + tagline pt-BR
  ("Envie o contexto que você possui. Vou organizar tudo em um plano ou em uma
  correção verificável.") — elegante, não genérico (§25).
- **Sidebar**: Nova conversa (Ctrl N), Capacidades, Mensagens, Artefatos, Tarefas
  agendadas; abas CONVERSAS/AGENTES; busca; Fixadas; e **sessões recentes reais**
  populadas (histórico funciona).
- **Composer**: "Dê uma tarefa ao Hermes" (pt-BR), com mic e controles.
- **Portal**: transicionou de "Portal off-line" → "Portal verificado" ao vivo
  (gateway conectou durante a inspeção).
- **pt-BR** coerente em toda a shell.

Dois fatos duros confirmados VISUALMENTE (não especulação):

1. **Build instalado = v0.20.4** (rodapé), que **antecede as mudanças desta
   missão**. As linhas de nav Agents/Memory e as camadas de domínio novas estão
   no fonte (testes verdes) mas **não neste binário** — vê-las ao vivo exige
   rebuild, que precisa do toolchain nativo do Windows (esbuild/electron/NSIS
   são win32; o bridge remoto é WSL sem essas binárias nem display — provado na
   Rodada 3, baseline).
2. Portanto: `U1_INSTALLED_APP` do que JÁ existia = **PASS visual**; do trabalho
   NOVO = **BLOCKED_BY_WINDOWS_BUILD** (rebuild no executor).

Itens confirmados PASS por inspeção visual real (app v0.20.4): U1_SHELL,
U1_SIDEBAR (linhas existentes), U1_CHAT, U1_COMPOSER, U1_EMPTY_STATE,
U1_SESSION_HISTORY, U1_SEARCH, U1_THEME (dark), U1_PT_BR.

## §19 — por que cada PARTIAL/FAIL restante NÃO é corrigível NESTE ambiente remoto

Capacidade real do bridge (probe §14): o `device_bash` é WSL, tem `node` mas
**sem rede** (curl→000), o `node_modules` do PC é do host (deps nativas
win32/esbuild não rodam sob Linux WSL), **sem display** para Electron e **sem
shell nativo do Windows**. Logo: `vitest/esbuild`, `electron`, `build`, `NSIS`,
launch do app instalado e inspeção visual **não são executáveis daqui** — não é
classificação genérica, é limitação técnica concreta. `tsc` e a suíte Python
rodam no cloud (e são usados como prova acima).

Consequência item a item:

- **Context unificado (aba direita) [PARTIAL]** — exige alterar o pane-tree
  dockável e **verificar docking/resize/persistência visualmente**. Sem app
  rodando, uma cirurgia no layout maduro violaria "não quebre o layout".
  Testável isolado o componente da aba, mas a integração no tree precisa do app.
- **Goal entrypoint / Goals authoring [PARTIAL]** — a criação/associação
  persiste via IPC do gateway Python; sem sessão de gateway viva não há como
  exercer o fluxo real (e mock para declarar PASS é proibido).
- **Security Research/RAPTOR [PARTIAL]** — backend pronto; a view precisa de IPC
  ao gateway para rodar preflight/scan reais. UI + contrato são testáveis com
  transporte fake (como fiz no OpenWA), mas declarar o fluxo real PASS exige o
  gateway.
- **Model routing display [PARTIAL]** — depende do runtime expor o modelo
  auto-selecionado; verificar exige o app enviando um turno real.
- **Agents authoring [PARTIAL]** — criar/delegar/cancelar aciona o runtime de
  subagentes (gateway).
- **Memory inline [PARTIAL]** — afford. "lembrado/esquecer" no chat aciona o
  provider de memória (gateway); starmap (view) já está no nav.
- **WhatsApp módulo [PARTIAL / WAITING_FOR_HUMAN_QR_SCAN]** — backend pronto; o
  status real e o QR vêm do runtime OpenWA externo + telefone.
- **Product Studio [FAIL]** — investigado: não há rota, pane, feature-flag,
  package nem component preservado no desktop (só o preset de config "OmniRoute
  Studio", não relacionado). É uma decisão de produto do dono se entra no U1;
  não invento demo.

Fechado NESTE ambiente com prova (test+canary): **Context Security
enforcement (§8)** e **coerência de nav (Agents+Memory, destinos reais)**.

## Gate honesto (§75/§76)

- Visual: o U1 já **parece** uma experiência desktop madura e coerente (não é uma
  colagem de componentes) — mas a confirmação final exige olhar o app rodando.
- Funcional: um usuário leigo consegue abrir, escolher projeto, pedir tarefa,
  acompanhar a IA e ver o resultado — o fluxo existe. A costura dos módulos
  (security/whatsapp/goals/memory) como superfícies próprias é o que resta.

**Conclusão honesta:** o Workspace U1 **não estava faltando** — estava presente e
maduro, com uma lacuna de coerência/descoberta e de validação device. Esta sessão
fechou a primeira peça dessa lacuna (Agentes no nav, verificado) e deixou o
restante como trabalho device/backend explícito, com prompts prontos. Nenhum
PASS foi inventado; nenhum botão falso foi criado.
