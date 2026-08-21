# HERMES OMNIROUTE — ARQUITETURA REAL

Mapeada a partir do código, não da documentação. Cada caixa referencia arquivos reais.

## 1. Topologia de processos

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ ELECTRON MAIN  (Node completo, sem sandbox)          apps/desktop/electron/  │
│  main.ts (15.2k linhas) · 142 ipcMain.handle + 23 ipcMain.on = 165 canais    │
│  session-windows.ts · hardening.ts · fs-ipc.ts · git-ipc.ts · terminal-ipc.ts│
│  bundled-product-studio.ts · omniroute-compression.ts   ← NOVOS (Studio)     │
└───────────────┬─────────────────────────────────────────────────────────────┘
                │  contextBridge (preload.ts, API nominal, sem canal dinâmico)
                │  contextIsolation:true  sandbox:true  nodeIntegration:false
┌───────────────▼─────────────────────────────────────────────────────────────┐
│ RENDERER  (React + Vite)                                  apps/desktop/src/  │
│  window.hermesDesktop → terminal.write, writeTextFile, openExternal,         │
│  git.*, trashPath, updates.apply, uninstall.run, omniRouteCompression, …     │
│  ⚠ SEM CSP   ⚠ webviewTag:true   ⚠ sem will-attach-webview                   │
│  <webview partition="persist:hermes-preview">  ← Preview de projeto          │
└───────────────┬─────────────────────────────────────────────────────────────┘
                │  hermes:api  →  HTTP/WS local
┌───────────────▼─────────────────────────────────────────────────────────────┐
│ BACKEND HERMES  (Python, processo filho)                                     │
│  gateway/ · agent/ · tools/ · hermes_cli/ · plugins/                         │
│  conversation_loop.py · tool_executor.py · approval.py · delegate_tool.py    │
└───┬───────────────┬───────────────┬──────────────────┬──────────────────────┘
    │               │               │                  │
    ▼               ▼               ▼                  ▼
┌────────┐   ┌────────────┐   ┌───────────┐   ┌─────────────────────────────┐
│ TOOLS  │   │  PLUGINS   │   │ DELEGAÇÃO │   │ MCP CLIENT                  │
│terminal│   │dz23-guard. │   │max_depth 2│   │ stdio → node bridge.mjs     │
│exec_cod│   │⚠ NÃO CARGA │   │max_child 5│   └───────────┬─────────────────┘
│file_*  │   │(HERMES-001)│   └───────────┘               │
│ssh     │   └────────────┘                               ▼
└────────┘                                   ┌─────────────────────────────┐
                                             │ omniroute-mcp-bridge.mjs    │
                                             │ ⚠ import() de TS via tsx    │
                                             │   a partir de env var       │
                                             │   (HERMES-002)              │
                                             └───────────┬─────────────────┘
                                                         ▼
                                             ┌─────────────────────────────┐
                                             │ OmniRoute MCP server 3.8.49 │
                                             │ 106 ferramentas             │
                                             │ escopos auto-concedidos     │
                                             │ (HERMES-003)                │
                                             └───────────┬─────────────────┘
                                                         ▼
                                  ┌──────────────────────────────────────────┐
                                  │ OmniRoute gateway  http://127.0.0.1:20128│
                                  │ ⚠ sem auth, sem verificação de identidade│
                                  │   (HERMES-016)  → provedores de modelo   │
                                  └──────────────────────────────────────────┘
```

## 2. Fluxo canônico UI → resultado → persistência

```text
1. Usuário digita no chat            src/app/session/…
2. Renderer → hermesDesktop.api()    preload.ts:188 → ipcMain 'hermes:api'
3. Main faz proxy HTTP local         → gateway Python
4. conversation_loop monta o turno   agent/conversation_loop.py
5. Modelo escolhe uma ferramenta
6. ▸ HOOK pre_tool_call              tool_executor.py:624-651   ⚠ fail-open (HERMES-014)
7. ▸ GATE de aprovação               tools/approval.py:4342-4985
      hardline → sudo → deny do usuário → yolo/off → allowlist →
      não-interativo → dangerous regex → SMART (LLM) → prompt humano
      ⚠ npm/pip install nem entra no fluxo (HERMES-011)
8. Execução                          terminal_tool / code_execution_tool (subprocesso RPC) /
                                     file_tools / ssh-connection / MCP
9. ▸ HOOK post_tool_call             (via model_tools)  → guardrail marca verified/changed
10. ▸ HOOK pre_verify                conversation_loop.py:8195  ⚠ nudge, teto 3 (HERMES-028)
11. Persistência                     hermes_state.py (SQLite) · memória · ~/.hermes
12. ▸ HOOK on_session_end            turn_finalizer.py:815 → relatório de tarefa
13. Streaming de volta               WS → renderer → UI
```

## 3. Trust boundaries

| # | Fronteira | O que atravessa | Controle existente | Estado |
|---|---|---|---|---|
| TB1 | Rede/web → renderer | HTML, títulos de link, favicon | nenhuma CSP | **FRACO** |
| TB2 | Renderer → main (IPC) | 165 canais, args do renderer | funções nomeadas; sem validação de origem do sender | **FRACO** |
| TB3 | Main → SO | shell.openPath, spawn, PTY, fs | allowlist de esquema (exceto `file:`), argv arrays | **PARCIAL** |
| TB4 | Modelo → ferramenta | args gerados pelo LLM | hardline floor + approval gate + guardrail | **PARCIAL** (guardrail inerte) |
| TB5 | Conteúdo externo → agente | web_fetch, arquivos, memória, respostas MCP, skills do GitHub | nenhum isolamento de instrução | **AUSENTE** |
| TB6 | Hermes → MCP OmniRoute | stdio + escopos declarados | escopos auto-concedidos | **AUSENTE** |
| TB7 | Studio → runtime Hermes original | escrita de plugin/bridge | marcador `.omniroute-managed.json` | **FRACO** |
| TB8 | Agente → SSH remoto | comandos remotos | `shq()` quoting, `--` antes do target | **BOM** |
| TB9 | Update → binário executado | git pull + updater | codesign fail-open (macOS), sem assinatura | **FRACO** |

## 4. Onde código não confiável entra

```text
A. omniroute_web_fetch / omniroute_web_search   → conteúdo web → contexto do agente
B. omniroute_github_skills_install              → INSTRUÇÕES de terceiros → contexto do agente
C. local_corpus_read / obsidian_read_note       → arquivos do usuário → contexto
D. omniroute_memory_add + memória do Hermes     → instruções persistentes entre sessões
E. Respostas de qualquer uma das 106 tools MCP  → texto não sanitizado → contexto
F. Preview <webview>                            → página do projeto em desenvolvimento
G. plugin_install (MCP) / hermes:plugin:installDesktop → código executável
H. OMNIROUTE_PACKAGE_ROOT                       → código executável (HERMES-002)
```

Nenhum desses caminhos marca a origem do texto como não confiável antes de entregá-lo ao modelo. A única defesa existente é o `_smart_approve`, que corretamente separa a política do operador (canal system) do comando (canal user, envolvido em `<command>`) — `tools/approval.py:3366-3383`. Essa boa prática **não** se estende ao conteúdo trazido por A–F.

## 5. Onde comandos, filesystem, rede e SSH podem ser acionados

```text
SHELL      terminal_tool → node-pty (main) ou subprocesso (backend)
           hermes:terminal:write — bytes crus, sem sanitização (por design)
           code_execution_tool → subprocesso Python isolado com RPC (bom)
FILESYSTEM file_tools (backend) · hermes:fs:{writeText,rename,trash,openDir,reveal} (main)
           ⚠ sem confinamento de raiz nos canais fs do main (HERMES-004)
           local_corpus_read · obsidian_* (via MCP)
REDE       hermes:api · fetchLinkTitle (curl) · omniroute_web_fetch · oneproxy_fetch
           update: git ls-remote + git pull
SSH        ssh-connection.ts · remote-lifecycle.ts · windows-remote-lifecycle.ts
           argv arrays, `--` antes do target, shq() nos comandos remotos
PROCESSO   spawn de emulador de terminal externo · updater staged · uninstaller
```

## 6. Componentes do Studio nos pontos corretos

```text
Product Studio  → skill em disco (HERMES_HOME/skills/…), carregada pelo backend.
                  É instrução para o modelo. Não é código executável.
Goal            → gateway/slash_commands.py + hermes_cli/cli_commands_mixin.py
                  Estado em goals.GoalManager (SQLite). Gate de pausa após draft.
Memory          → habilitada via config (memory_enabled, user_profile_enabled)
                  + omniroute_memory_* via MCP (superfície paralela, não integrada)
Preview         → <webview> no renderer, partition isolada, sem processo servidor próprio
SSH             → módulos electron/ssh-*.ts, perfis em connection-registry
Caveman         → toggle na UI → IPC → execFile(node, bridge --compression-set) →
                  compressionTools.ts do OmniRoute. Allowlist de modo correta.
Guardrails      → plugin Python (INERTE, HERMES-001) + approvals do core (ativo)
Cron            → omniroute-daily-health.py agendado pelo cron do Hermes (cron/)
```

## 7. Duas superfícies de memória concorrentes (achado arquitetural)

O Studio habilita a memória nativa do Hermes (`memory.memory_enabled`) **e** concede `read:memory`/`write:memory` às ferramentas `omniroute_memory_*` do MCP. São dois armazenamentos distintos, sem sincronização, sem política comum de retenção e sem fronteira de isolamento comum. O mesmo vale para skills: `skills/` do Hermes × `omniroute_skills_*` e `omniroute_github_skills_install`.

Não é um bug hoje, mas é dívida arquitetural direta: duas fontes de verdade para "o que o agente lembra" e "o que o agente sabe fazer", com modelos de permissão diferentes. Está no plano de melhoria como `SHOULD_FIX`.
