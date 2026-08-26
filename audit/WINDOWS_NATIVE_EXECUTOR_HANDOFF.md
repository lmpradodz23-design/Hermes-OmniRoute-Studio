# HERMES — WINDOWS NATIVE EXECUTOR HANDOFF (Runtime Wiring → Build → E2E)

> PARA: uma sessão **Claude Code / Codex rodando NATIVA no Windows**, dentro do repo
> `C:\Users\zodyp\Documents\Codex\Hermes-OmniRoute`, no branch **`develop`**
> (já em `51a81b8`, com os 29 commits de kernel/factory/provider integrados).
>
> POR QUE ESTE DOC EXISTE: o bridge de nuvem (VM Linux, sem rede, sem toolchain
> Windows, GUI mascarada) **não pode** buildar Electron/NSIS, instalar o app, abrir
> a GUI, nem fazer health checks reais. Essas etapas são **WINDOWS_EXECUTABLE_INTERNAL_WORK**
> e só um executor nativo as roda. O código-fonte puro (os 29 commits) já está no
> `develop`. Este handoff diz **como CONSUMI-LO no produto real e validar**.

## ✅ SOURCE-VALIDÁVEL JÁ CONCLUÍDO (não reescrever — só conectar/validar em runtime)
Estes adapters/contratos já existem no `develop`, testados (37 testes de contrato, sem rede/GUI):
- `agent/provider_omniroute_bridge.py` — routing decision → `ProviderProfile` real (reconcile), fail-closed,
  LOCAL_ONLY absoluto, ASK_BEFORE_PAID, config sanitizada p/ o transport existente. → **Fase A**
- `agent/provider_secret_bridge.py` — reusa `agent/secret_sources/`; guarda só handle não-secreto;
  `ErrorKind→ConnectionStatus`; key crua fica in-process. → **Fase B**
- `agent/provider_probe.py` — `HttpClient` injetável; `classify_http_status/exception`, `parse_models`
  (OpenAI+Ollama), `health_check`, `detect_local` (só 127.0.0.1). → **Fases A/parte de saúde+discovery+local**
- `agent/provider_settings_service.py` — view-model + máquina de estados do connect (format→store→resolve→
  health→discover→CONNECTED) + handlers IPC (dict) renderer-safe. → **Fase C (lógica)**
- `agent/provider_runtime_hooks.py` — `route_history`/`benchmark_arena`/`mission_trace`/`mission_evidence`
  + `route_for_mission()`. → **Fases A/D (integração de rota+evidência+aprendizado)**

**O QUE FALTA (só o que depende de runtime real) — é o SEU trabalho, executor Windows:**
- Injetar as implementações reais: `HttpClient` (requests/httpx), `SecretResolver`/`secret_writer`
  (Windows Credential Manager/DPAPI ou keytar via um novo `SecretSource`), e o `registry` = `providers/`.
- Renderizar a tela React (`apps/desktop/src/app/settings/ai-models-settings.tsx`) consumindo `ipc_get_view`
  e `ProviderSettingsService.connect`.
- Ligar `route_for_mission()` ao dispatch de missão real do Hermes.
- Rodar health/discovery/local-detect REAIS (rede + Ollama/LM Studio locais) e provar LOCAL_ONLY zero-egress.
- Build/package/NSIS/install/E2E.

## INVARIANTES (valem para TODAS as fases — nunca violar)
- `SOURCE_IMPLEMENTED != PRODUCT_INTEGRATED`. Não reimplemente os 29 commits; faça **adapters/wiring mínimo**.
- **NUNCA invente PASS.** Separe IMPLEMENTATION/UNIT/CONTRACT/INTEGRATION(source) de REAL_RUNTIME/E2E.
- **Sem mock para declarar runtime PASS.** Runtime PASS exige o app real rodando.
- **Segredos:** API key nunca em repo, renderer persistence, localStorage, logs, task reports, screenshots.
  Use o mecanismo existente `agent/secret_sources/` (OS-backed). Renderer recebe só `{configured, status, metadata}`.
- **LOCAL_ONLY absoluto:** egress cloud = ZERO, mesmo que o provider cloud seja grátis/top score.
- **ASK_BEFORE_PAID:** nenhuma chamada paga sem autorização explícita.
- **Git:** nunca push no upstream NousResearch; nunca force push; nunca release stable/tag.
  Integrar em `develop` do fork `oss` (lmpradodz23-design/Hermes-OmniRoute-Studio).
- A cada fase: rode os comandos de verificação, grave evidência em `audit/runtime-evidence/<sha>/`,
  e atualize `audit/AUTONOMOUS_HERMES_CHECKPOINT.md`. Continue enquanto `WINDOWS_EXECUTABLE_INTERNAL_WORK > 0`.

## SEAMS REAIS (já localizados — use estes, não procure de novo)
- Registry de providers (execução OmniRoute): `providers/__init__.py` → `get_provider_profile(name)`,
  `list_providers()` → `ProviderProfile` (`providers/base.py`).
- Execução do request: `agent/transports/chat_completions.py::_build_kwargs_from_profile()`.
- Módulos novos a consumir (NÃO recriar): `agent/provider_catalog.py`, `agent/provider_routing.py`,
  `agent/provider_adapter.py`, `agent/provider_catalog_link.py`, `agent/provider_settings_view.py`.
- Secret storage existente: `agent/secret_sources/` — `registry.register_source/get_source/list_sources`,
  ABC `SecretSource.fetch(cfg, home_path) -> FetchResult` (`base.py`), backends `command.py`/`onepassword.py`/`bitwarden.py`.
- Settings UI: `apps/desktop/src/app/settings/*.tsx` (React). Build/preview: `apps/desktop` (vite + electron).
- Kernel novo (a ligar no runtime): `agent/mission_*.py`, `agent/route_history.py`, `agent/benchmark_arena.py`,
  `agent/capability_acquisition.py`, `agent/security_gate.py`, `agent/safe_repair.py`, `agent/self_heal.py`,
  `agent/doctor_model.py` — todos com testes em `tests/agent/` e `tests/canary/`.

---

## FASE A — PROVIDER CATALOG NO OMNIROUTE REAL (itens 1,5,6,7,8,9,10)
**Objetivo:** o gateway escolhe provider via `provider_routing.select_provider()` (free-first/LOCAL_ONLY/cost-guard),
resolvendo a `ProviderProfile` existente por `provider_catalog_link.reconcile()`.

Passos:
1. Adapter fino `agent/provider_omniroute_bridge.py` que:
   - chama `reconcile(ProviderCatalog(), providers)` (duck-typed já compatível com `providers/__init__.py`);
   - monta `ProviderCandidate`s a partir de: catálogo + estado de conexão (secret configurado?) + `benchmark_arena` (quality_score) + latência conhecida;
   - chama `select_provider(..., local_only, profile, paid_authorized)`;
   - devolve o `ProviderProfile` real do escolhido para o caminho `_build_kwargs_from_profile()`.
   - **NÃO** duplicar o transporte; só escolher qual profile entra nele.
2. Health check real (`provider_adapter`): implemente probes injetáveis — cloud: `GET {api_base}/models` com a key resolvida do secret source; local: `local_health_url()`. Classifique em `ConnectionStatus` (CONNECTED/INVALID_KEY/NO_QUOTA/RATE_LIMITED/NETWORK_ERROR/PROVIDER_DOWN/CONFIG_ERROR).
3. Model discovery real: liste modelos do `/models` (ou `/api/tags` no Ollama). Cache curto.
4. Auto-detecção local: tente `127.0.0.1` Ollama(11434)/LM Studio(1234)/vLLM(8000) — só localhost.
5. FREE_FIRST/LOCAL_ONLY/ASK_BEFORE_PAID: exercite os 3 canários do §37 já existentes **contra o caminho real** (não o de teste).

**NÃO FAZER:** criar roteador paralelo; inventar cotas; chamar provider pago sem `paid_authorized`;
em LOCAL_ONLY, tocar em qualquer provider cloud.

**Verificar:**
```
python -m pytest tests/agent/test_provider_layer.py tests/agent/test_provider_link_view.py -q
python -m pytest tests/agent/test_provider_omniroute_bridge.py -q   # criar: bridge escolhe o profile certo
# health/discovery: teste com Ollama local rodando (sem rede externa) -> CONNECTED + lista de modelos
# LOCAL_ONLY: capture egress (ex: proxy/log) e prove 0 requisições cloud
```
Evidência: salvar saída de discovery local + prova de zero-egress LOCAL_ONLY.

---

## FASE B — SECURE STORAGE REAL (item 2)
**Objetivo:** persistir a API key via mecanismo OS-backed existente; renderer nunca vê o segredo.
Passos:
1. Adicione um `SecretSource` OS-backed (Windows Credential Manager / DPAPI, ou `keytar` no lado Electron)
   em `agent/secret_sources/` seguindo a ABC (`fetch`, `is_enabled`, `config_schema`, `remediation`).
   Registre via `register_source(...)` no bootstrap (`_ensure_builtin_sources`).
2. `ProviderConfig.key_ref` (já existe, sem campo `api_key`) aponta para a entrada no secret source.
3. IPC Electron: renderer manda a key UMA vez para o main; main grava no secure store; renderer recebe de volta só `sanitize_for_renderer()` → `{configured:true, status, metadata}`.

**NÃO FAZER:** gravar key em arquivo do repo, `localStorage`, log, task report, screenshot.

**Verificar:**
```
python -m pytest tests/agent/test_provider_layer.py -k secret -q      # sanitize/no api_key field
# manual: configure uma key fake -> confirme que grep -r na key NÃO acha nada em repo/logs/renderer store
# reabrir o app -> configured=true persiste; key nunca trafega pro renderer
```

---

## FASE C — SETTINGS → IA & MODELOS REAL (itens 3,4)
**Objetivo:** tela leiga consumindo `provider_settings_view.build_settings_view()`.
Passos (em `apps/desktop/src/app/settings/`, novo `ai-models-settings.tsx`):
1. IPC que chama o Python `build_settings_view(catalog, configured, statuses, executable, local_only)` e devolve o view-model **já sanitizado**.
2. Render: seções **Recomendados / Locais / Grátis sem cartão / Mais**; card com nome, status, grátis/pago/local, capabilities, `[Conectar]`.
3. Fluxo Conectar (guided): instrução simples → "Obter chave" (`get_key_url`, abre no browser) → colar key → `validate_key_format` (client) → gravar no secure store (Fase B) → health check (Fase A) → CONNECTED.
4. Ações: `[Configurar melhores opções grátis]` (usa `quick_start_provider_id`), `[Testar todos]` (health em paralelo).
5. Sem exigir JSON/terminal/model-id no fluxo comum.

**Verificar:** unit/component tests (vitest/RTL) da tela + e2e Playwright do fluxo Conectar (`apps/desktop/e2e`).
Screenshot do fluxo → `audit/runtime-evidence/<sha>/settings-ai-models.png`.

---

## FASE D — AUTONOMY KERNEL NO RUNTIME (itens 11,12,13)
**Objetivo:** Mission/DAG/Store/Runtime/Scheduler/Watchdog/Evidence/RouteHistory/CapabilityAcquisition/
SecurityGate/SafeRepair/BenchmarkArena deixam de ser libs isoladas e passam a rodar o fluxo real de missão.
Passos:
1. Ponto de entrada de missão do Hermes (goals/kanban): ao criar uma missão, construir `MissionDag`
   (via `product_spec.to_mission_dag()` quando for factory) e rodar com `MissionRuntime` + `make_dispatch_policy`.
2. Persistir com `MissionStore` (SQLite) — sobreviver a restart; `checkpoint/resume` reais.
3. Evidence Engine por nó; correlação via `mission_trace` (logs redigidos).
4. Capability Acquisition: injetar `inject_acquire_node` quando faltar ferramenta (ver Fase E).
5. Integration tests reais (não unit puro): missão pequena ponta-a-ponta no runtime.

**NÃO FAZER:** editar os módulos (só wiring); declarar PASS sem uma missão real completando.

**Verificar:**
```
python -m pytest tests/agent/test_full_kernel_integration.py -q
# + novo tests/agent/test_runtime_mission_smoke.py: missão real via runtime persiste, cai, resume, completa
```

---

## FASE E — CAPABILITY ACQUISITION REAL (item 13)
Missão controlada que exige uma ferramenta ausente. Hermes deve, **sem humano para dependência low-risk**:
detect → evaluate → acquire safely → install isolated → smoke test → register → resume ORIGINAL mission → complete.
Hard-stop de segurança (§163) para HIGH/EXTERNAL. **Verificar:** o gate §165 (adquire + completa sem humano).

## FASE F — EYES & HANDS REAIS (itens 14,15,16)
- **Computer Use** (tooling existente): observe/click/type/scroll/focus/launch/verify em app controlado; grave Evidence.
- **Browser** real: navigate/DOM/click/type/console/network/screenshot/responsive; **sem importar cookies pessoais**.
- **Visual QA**: fixture visual defeituosa → open→observe→detect→report→fix→reopen→verify.

## FASE G — CREATIVE / SELF-HEALING (itens 17,20)
- Creative/Image: ligar `plugins/image_gen` ao `creative_contract`; LOCAL_ONLY impede image provider cloud; nada pago sem auth.
- Self-Healing: falha interna controlada → detect → internal mission → **isolated** repair (propose-only) → test → evidence → integration proposal. **Nunca** editar instalação ativa cegamente.

## FASE H — SECURITY / DOCTOR (itens 18,19)
- `security_gate` como mission gate real (SECURITY_REVIEW→remediation→rescan→reopen). RAPTOR binário = BLOCKED_PLATFORM se ausente.
- `doctor_model` + `safe_repair` ligados a `hermes_cli/doctor.py` (status BLOCKED + ponte self-heal).

## FASE I — BUILD / PACKAGE / NSIS (itens 21,22,23)
Só depois do wiring acima passar:
```
# raiz e apps/desktop:
<lint>  <typecheck>  <unit>  <integration>  <python pytest>
cd apps/desktop && npm ci && npm run build && npm run electron:build   # ajustar aos scripts reais do package.json
# NSIS: gerar instalador Windows (electron-builder win nsis)
```
Registrar SHASUMs dos artefatos.

## FASE J — INSTALAÇÃO + P0 UPDATER (itens 24,25,+P0)
Instale a **nova** versão (não testar a v0.20.4 antiga). Confirme `SOURCE_HEAD == PACKAGE_VERSION == INSTALLED_VERSION`.
No binário novo, prove: cold start, restart, fork guard, update failure, persisted backoff, backend READY.
Só então `P0_UPDATER_RUNTIME=PASS`.

## FASE K — INSTALLED E2E + AUDITORIA FINAL (itens 26–30)
No app instalado: new mission → ProductSpec → DAG → OmniRoute → agents/tools → evidence → browser/computer → result.
Depois close → reopen → resume. Failure injection. Restart/resume. Inspeção visual.
Auditoria final independente (Architect / Security / Product-QA) → `audit/FINAL_THREE_AGENT_REVIEW.md`.

---

## FINAL GATE
Recalcular `WINDOWS_EXECUTABLE_INTERNAL_WORK`. Continuar enquanto `> 0`.
Parar só quando `OPEN_INTERNAL_FIXABLE=0` **ou** o restante for comprovadamente
`WAITING_FOR_HUMAN` / `BLOCKED_EXTERNAL` / `BLOCKED_PLATFORM` / `LEGAL_REVIEW_REQUIRED`,
com evidência. Não inventar PASS. Não reimplementar os 29 commits. Não push upstream. Não release stable.
