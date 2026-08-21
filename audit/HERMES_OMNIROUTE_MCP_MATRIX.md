# HERMES OMNIROUTE — MATRIZ DAS FERRAMENTAS MCP

Fonte: pacote `omniroute@3.8.49` instalado em `%APPDATA%\npm\node_modules\omniroute`, enumerado estaticamente.

## Método e limite de prova

**Nenhuma chamada viva foi executada.** O servidor MCP não foi iniciado neste ambiente (exigiria o runtime Windows). Portanto:

- `discovered` = **FATO**, extraído das definições de ferramenta no pacote.
- `schema_valid` = **FATO** onde a ferramenta está em `MCP_TOOL_MAP` (schema Zod presente) ou traz `inputSchema` na coleção.
- `authorization` = **FATO**, derivado dos escopos declarados × escopos concedidos pelo Hermes (`main.ts:14432-14444`).
- `call_tested`, `result_valid`, `error_handling`, `timeout` = **NOT_TESTED** para todas as 106.
- `guardrail` = **NONE** para todas, porque o `dz23-guardrail` não carrega (HERMES-001) e ele não intercepta chamadas MCP de qualquer forma — seu `pre_tool_call` recebe nomes de ferramenta do Hermes, não do MCP.

**Não transformei `discovered=true` em `PASS`.** Todas as 106 estão `NOT_TESTED`.

## Contagem

```text
TOTAL_EXPECTED=107
TOTAL_DISCOVERED=106
PASS=0
PARTIAL=0
FAIL=0
BLOCKED=0
NOT_TESTED=106
DIVERGENCE=1 (ver HERMES-032; requer tools/list contra o servidor vivo)
```

## Escopos concedidos pelo Hermes (32) — todos, por default

```text
execute:completions  execute:search  execute:skills  pricing:write
read:cache  read:catalog  read:combos  read:compression  read:gamification
read:health  read:local-corpus  read:memory  read:models  read:notion
read:obsidian  read:plugins  read:proxies  read:quota  read:skills
read:tools  read:usage
write:budget  write:cache  write:combos  write:compression  write:gamification
write:memory  write:notion  write:obsidian  write:plugins  write:resilience  write:skills
```

⚠ **HERMES-003:** o servidor usa essa mesma lista como os escopos do chamador (`server.ts:225`). Toda coluna `authorization` abaixo é, na prática, `GRANTED`.

## Matriz por categoria

Colunas: `discovered | schema | call_tested | authorization | risco | status`

### Roteamento e saúde — 20 ferramentas · risco BAIXO

| tool | schema | escopo | risco | status |
|---|---|---|---|---|
| omniroute_get_health | ✔ MCP_TOOL_MAP | read:health | BAIXO | NOT_TESTED |
| omniroute_list_combos | ✔ | read:combos | BAIXO | NOT_TESTED |
| omniroute_get_combo_metrics | ✔ | read:combos | BAIXO | NOT_TESTED |
| omniroute_switch_combo | ✔ | write:combos | MÉDIO — muda o roteamento de todos os turnos | NOT_TESTED |
| omniroute_check_quota | ✔ | read:quota | BAIXO | NOT_TESTED |
| omniroute_route_request | ✔ | execute:completions | MÉDIO — consome crédito | NOT_TESTED |
| omniroute_cost_report | ✔ | read:usage | BAIXO | NOT_TESTED |
| omniroute_list_models_catalog | ✔ | read:models | BAIXO | NOT_TESTED |
| omniroute_simulate_route | ✔ | read:health+combos | BAIXO | NOT_TESTED |
| omniroute_set_budget_guard | ✔ | write:budget | **ALTO** — desativar o teto de gasto | NOT_TESTED |
| omniroute_set_routing_strategy | ✔ | write:combos | MÉDIO | NOT_TESTED |
| omniroute_set_resilience_profile | ✔ | write:resilience | MÉDIO | NOT_TESTED |
| omniroute_test_combo | ✔ | execute:completions+read:combos | MÉDIO | NOT_TESTED |
| omniroute_get_provider_metrics | ✔ | read:health | BAIXO | NOT_TESTED |
| omniroute_best_combo_for_task | ✔ | read:combos+health | BAIXO | NOT_TESTED |
| omniroute_explain_route | ✔ | read:health+usage | BAIXO | NOT_TESTED |
| omniroute_get_session_snapshot | ✔ | read:usage | MÉDIO — snapshot pode conter prompt | NOT_TESTED |
| omniroute_db_health_check | ✔ | read:health+write:resilience | MÉDIO | NOT_TESTED |
| omniroute_sync_pricing | ✔ | pricing:write | BAIXO | NOT_TESTED |
| omniroute_pick_fastest_model | ✔ schemas/pickFastestModel | — | BAIXO | NOT_TESTED |

### Rede e proxy — 5 · risco **ALTO** (SSRF + entrada não confiável)

| tool | escopo | risco | observação |
|---|---|---|---|
| omniroute_web_search | execute:search | **ALTO** | traz conteúdo web para o contexto do agente |
| omniroute_web_fetch | execute:search | **ALTO** | SSRF + vetor primário de prompt injection indireto |
| omniroute_oneproxy_fetch | read:proxies | **ALTO** | fetch proxied — contorna políticas de rede locais |
| omniroute_oneproxy_rotate | read:proxies | MÉDIO | |
| omniroute_oneproxy_stats | read:proxies | BAIXO | |

Todas `NOT_TESTED`. **Nenhuma marcação de origem não confiável no retorno.**

### Cache e compressão — 8 · risco BAIXO/MÉDIO

`omniroute_cache_stats` (read:cache) · `omniroute_cache_flush` (write:cache, MÉDIO — perda de cache) · `omniroute_compression_status` · `omniroute_compression_configure` · `omniroute_set_compression_engine` · `omniroute_list_compression_combos` · `omniroute_compression_combo_stats` (+8 internas em `compressionTools.ts`) — todas `NOT_TESTED`.

**Nota:** `omniroute_set_compression_engine` é a mesma capacidade que o toggle do Caveman aciona pelo CLI. Existem **dois caminhos** para o mesmo estado (CLI da bridge e ferramenta MCP), com validação diferente: o CLI valida o modo (`bridge.mjs:50`), a ferramenta MCP aceita o que o schema permitir.

### CCR (context/cache references) — 6 · risco MÉDIO

`omniroute_ccr_store` · `_retrieve` · `_inspect` · `_list` · `_delete` · `_stats`. Armazenam e recuperam conteúdo de contexto. `_delete` é destrutivo. Todas `NOT_TESTED`.

### Memória — 3 · risco **ALTO**

| tool | escopo | risco |
|---|---|---|
| omniroute_memory_add | write:memory | **ALTO** — injeção persistente entre sessões |
| omniroute_memory_search | read:memory | MÉDIO |
| omniroute_memory_clear | write:memory | **ALTO** — perda de dados |

Superfície de memória **paralela** à memória nativa do Hermes, sem política comum. Ver ARCHITECTURE §7.

### Skills — 7 · risco **CRÍTICO**

| tool | escopo | risco |
|---|---|---|
| omniroute_skills_list | read:skills | BAIXO |
| omniroute_skills_enable | write:skills | **ALTO** |
| omniroute_skills_execute | execute:skills | **CRÍTICO** — executa skill |
| omniroute_skills_executions | read:skills | BAIXO |
| omniroute_github_skills_search | read:catalog | MÉDIO |
| omniroute_github_skills_scan | read:catalog | MÉDIO |
| omniroute_github_skills_install | write:skills | **CRÍTICO** — instala INSTRUÇÕES de terceiros que o agente depois segue |

`omniroute_github_skills_install` + `omniroute_skills_execute` formam a cadeia mais perigosa do catálogo: conteúdo arbitrário do GitHub vira comportamento do agente, com `write:skills` e `execute:skills` concedidos por default. **Todas NOT_TESTED e sem guardrail.**

### Agent skills — 3 · risco BAIXO
`omniroute_agent_skills_list` · `_get` · `_coverage` (read:catalog).

### Plugins — 8 · risco **CRÍTICO**

`plugin_install` · `plugin_uninstall` · `plugin_activate` · `plugin_deactivate` · `plugin_configure` · `plugin_list` · `plugin_scan` · `plugin_executions` — escopo `write:plugins`/`read:plugins`, **concedido por default**.

Instalar e ativar plugin é execução de código. Esta categoria sozinha justifica a correção de HERMES-003.

### Obsidian — 22 · risco **ALTO** (filesystem do usuário)

Leitura: `obsidian_read_note`, `_list_vault`, `_search_simple`, `_search_structured`, `_get_note_metadata`, `_get_document_map`, `_get_tags`, `_get_active_file`, `_get_periodic_note`, `_check_status`, `_list_commands`, `_sync_status`, `_sync_conflicts`.
**Escrita/destrutivas:** `obsidian_write_note`, `_append_note`, `_patch_note`, `_move_note`, **`obsidian_delete_note`**, `_open_file`, `_sync_trigger`, `_sync_resolve_conflict`, e **`obsidian_execute_command`** — execução de comando arbitrário do Obsidian.

Escopos `read:obsidian`/`write:obsidian` concedidos por default. Todas `NOT_TESTED`. Se o usuário não usa Obsidian, essas 22 são superfície pura sem benefício.

### Notion — 6 · risco MÉDIO/ALTO
`notion_search` · `_get_page` · `_get_database` · `_query_database` · `_list_block_children` · **`notion_append_blocks`** (escrita externa). Escopos concedidos por default.

### Corpus local — 3 · risco **ALTO**
`local_corpus_read` · `_search` · `_status` — leitura de filesystem por um caminho paralelo ao `file_tools` do Hermes, portanto **fora** de qualquer política do Hermes.

### Gamificação — 8 · risco MÉDIO
`gamification_profile` · `_badges` · `_rank` · `_leaderboard` · `_servers` · `_anomalies` · **`gamification_invite`** · **`gamification_transfer`** — as duas últimas fazem ações sociais/de transferência externas.

### Pool de browser — 6 · risco MÉDIO
`omniroute_pool_status` · `_health` · `_sessions` · `_warm` · `_reset` · `omniroute_browser_pool_status`.

### Busca de ferramentas — 1
`omniroute_tool_search` (read:tools).

## Recomendação de escopo mínimo

Para um produto voltado a construir software, o conjunto default deveria ser:

```text
read:health  read:models  read:combos  read:quota  read:usage  execute:completions
```

E opt-in explícito, com consentimento por categoria na UI, para: `execute:search` (web), `write:memory`, `*:obsidian`, `*:notion`, `read:local-corpus`, `*:gamification`, `read:proxies`, `*:skills`, e **especialmente** `write:plugins`.

Isso reduz a superfície de 106 ferramentas para ~20 no caminho default, sem remover funcionalidade — apenas exigindo que o usuário a ative conscientemente.
