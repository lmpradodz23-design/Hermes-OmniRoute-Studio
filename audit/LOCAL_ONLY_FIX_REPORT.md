# LOCAL_ONLY — fechamento do egress auxiliar (era FAIL)

Data: 2026-08-23. Evidência: pytest em venv isolado (HOME isolado), container Linux.

## Problema (auditado no código)
`authorize_route` existia só em `conversation_loop.py` (rota principal) e `local_only.py`.
O SEGUNDO chokepoint de egress — `agent/auxiliary_client.py` — não consultava política:
compression, title, **visão**, MoA, one-shot, plugin-LLM e o **fallback cloud em falha/402**
podiam enviar conteúdo a provider remoto mesmo em local_only. `image_generate`/
`video_generate` (fal.ai) idem.

## Correção (causa raiz, centralizada)
Enforcement fail-closed no ponto onde os clients são construídos, para que novos call
sites não escapem:

1. `agent/local_only.py`: `LocalOnlyViolation` + `egress_denial_reason(provider, base_url)`
   — mesma regra de loopback do `authorize_route` (uma fonte de verdade). Adicionados
   `image_generate`/`video_generate` ao denylist de tools de rede.
2. `agent/auxiliary_client.py`:
   - `_enforce_local_only_egress(base_url)` — lê o flag `local_only` do ContextVar
     `_RUNTIME_MAIN_CONTEXT`; se ativo e rota não-loopback → `raise LocalOnlyViolation`.
   - Chamado em `_create_openai_client` (factory central dos 15+ sites, cobre visão e
     **fallback**, que constroem por ela) e nas 2 construções `GeminiNativeClient`.
   - Chamado no factory **async** (`AsyncOpenAI`, usado pelo MoA/streaming) — o path async
     não passa pelo factory sync.
   - `set_runtime_main(..., local_only: bool)` passa a carregar o flag no contexto do turn.
3. `agent/turn_context.py`: publica `local_only=agent._local_only_policy.config.enabled`
   ao estabelecer o contexto do turn.

## Revisão adversarial → correção (importante, não escondido)
Um auditor adversarial independente REPROVOU a primeira versão: o gate cobria só clients
OpenAI-compatíveis + 2 sites Gemini; os **adapters nativos** (Anthropic/Bedrock/Vertex/
Gemini-native/Codex) constroem seus próprios clients e **escapavam** (o gate async ficava
DEPOIS dos early-returns por isinstance). Corrigido:
- `_to_async_client`: gate no **TOPO** (antes dos early-returns) → todo async nativo coberto.
- `resolve_provider_client`: virou um **wrapper** que enforça no client resolvido → todo
  sync nativo do produtor principal coberto num único ponto.
- cadeia de fallback (`_get_provider_chain`): pula provider bloqueado (um fallback loopback
  posterior ainda pode vencer) — cobre "local falha → cloud" com precisão.
- Predicado único `_local_only_denial` (raising `_enforce_local_only_egress` + skip na cadeia).

## Cobertura (testada)
| Família | Estado | Como |
|---|---|---|
| rota principal | gated (já existia) | conversation_loop authorize_route |
| aux sync (compression/title/oneshot/plugin) | **gated** | `_create_openai_client` |
| visão | **gated** | usa `_create_openai_client` |
| fallback cloud (falha/402) | **gated** | `_create_openai_client` + skip na cadeia |
| aux async / MoA streaming | **gated** | topo de `_to_async_client` + factory `AsyncOpenAI` |
| **adapters nativos** (Anthropic/Bedrock/Vertex/Gemini-native/Codex) | **gated** | topo de `_to_async_client` + wrapper `resolve_provider_client` |
| Gemini nativo (pool) | **gated** | 2 sites + topo de `_to_async_client` |
| image/video generation | **gated** | `authorize_tool` denylist |
| web/browser/notion/composio | gated (já existia) | `authorize_tool` |
| propagação a thread pool (copy_context) | **gated + testado** | teste cruza `copy_context().run()` |

## Prova (pytest isolado)
- `tests/agent/test_local_only_aux_egress.py`: **24 passed** (inclui adapters nativos via
  subclasse real de `AnthropicAuxiliaryClient` no early-return, wrapper `resolve_provider_client`,
  e propagação por `copy_context().run()` em thread) — matriz de rotas cloud
  (OpenAI/Anthropic/Gemini/OpenRouter/Azure/base_url-vazio/genérica) DENY; rotas loopback
  (localhost/127.0.0.1/host.docker.internal/local-provider-sem-base_url) ALLOW; chokepoint
  real `_create_openai_client` bloqueia cloud, bloqueia base_url vazio (default = cloud),
  permite loopback, permite cloud com local_only OFF, no-op sem contexto; gen-tools DENY.
- `tests/agent/test_local_only.py` (rota principal): **8 passed** (sem regressão).
- **Canary verificado:** removido o `_enforce_local_only_egress(base_url)` → 2 testes do
  chokepoint falham ("DID NOT RAISE"); restaurado → verde.
- Sanidade: `agent.turn_context`, `agent.auxiliary_client`, `agent.local_only` importam OK.

## Classificação honesta
`LOCAL_ONLY = SOURCE_PASS (egress de modelo sync+async+Gemini + gen-tools, turn-scoped)`.

## Revisão adversarial de 3 agentes (§25) — achados e correções
- **Security agent** REPROVOU v1: adapters nativos escapavam → **corrigido** (topo de
  `_to_async_client` + wrapper `resolve_provider_client`) + P2 do `applyUpdates` sem `catch`
  → **corrigido** (backstop fail-safe).
- **Architecture agent** achou P2: o skip da cadeia de fallback era dead-code (os builders
  agora LEVANTAM antes do post-check) e sem `try/except` a exceção abortava a cadeia →
  **corrigido** (try/except em `_try_payment_fallback` e `_resolve_auto_route` Step 3 +
  belt-and-suspenders nos dois) + teste que prova "cloud pula, loopback vence".
- **QA agent** (mutation testing) achou: (a) os gates Gemini-native por-site (2775/2816)
  não tinham canary → agora são uma **terceira camada redundante**: o wrapper
  `resolve_provider_client` e o **post-check** de `_resolve_auto_route` Step 3 (adicionado)
  pegam o `GeminiNativeClient` cloud, e há teste com canary para o post-check; (b) a
  ORQUESTRAÇÃO de `applyUpdates` (main.ts) não tem teste unitário → ver residual abaixo.

### Residuais (NÃO cobertos — registrados, não escondidos)
0. **Orquestração de `applyUpdates` (main.ts)** não é unit-testável (importa Electron). Os
   HELPERS puros que ela chama (`collectInstallState`, `decideUpdateGate`, `parseBackoffState`)
   têm testes+canaries, mas o wiring (`!collected.ok` → skip; outer catch fail-safe; backoff
   nas saídas) é validado só pela **matriz de runtime do Windows** (`U1_WINDOWS_FINAL_EXECUTOR.md`
   §6). Extrair o core do `applyUpdates` sem runtime seria refactor arriscado da função de
   boot — deixado como tarefa de executor, não landado às cegas.
1. **Chamadas auxiliares FORA de um turn** (jobs de fundo/cron que constroem client sem
   `set_runtime_main(local_only=True)` no contexto) não são gated. As chamadas do turn
   (compression/title/visão) são cobertas por herança de ContextVar. *Fix:* fazer o
   caminho de background ler o config persistido; ou publicar o contexto também nesses
   workers. → executor.
2. **`agent/account_usage.py`** faz GET a `api.anthropic.com/.../usage` (metadados de uso,
   sem conteúdo de documento) sem gate. Severidade baixa. *Fix:* gate explícito.
3. **Embeddings**: não encontrei caminho de embedding cloud que ignore o factory; confirmar
   em runtime no executor.

`RUNTIME` de LOCAL_ONLY (app instalado, rede observada) fica para o Executor Windows (§7 do
`U1_WINDOWS_FINAL_EXECUTOR.md`).
