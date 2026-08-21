# PROMPT PARA O CODEX — HERMES OMNIROUTE STUDIO: CORREÇÃO E EVOLUÇÃO

> Este documento é autossuficiente. Você não precisa procurar mais nada para começar. Leia-o inteiro antes de tocar em qualquer arquivo.

---

## 0. REGRAS INEGOCIÁVEIS

> **Você não está autorizado a esconder problemas para obter um pipeline verde.**
>
> **Corrija a causa raiz.**
>
> **Não remova testes para fazê-los passar.**
>
> **Não enfraqueça assertions.**
>
> **Não substitua integrações reais por mocks para declarar sucesso.**
>
> **Não transforme FAIL em PASS por alteração de relatório.**
>
> **Não remova funcionalidades problemáticas como forma de corrigir bugs.**
>
> **Preserve o Hermes original e minimize alterações invasivas no core.**
>
> **Revise os 58 arquivos staged e os findings abaixo antes de modificar qualquer coisa.**
>
> **Após cada correção relevante, execute o teste específico e posteriormente a regressão completa.**

Estado inicial de Git obrigatório:
```text
DO_NOT_COMMIT_YET
DO_NOT_PUSH_YET
```
Nunca execute, sobre o trabalho existente, sem necessidade comprovada e autorização explícita do usuário:
```text
git reset --hard
git clean -fd
git checkout .
git restore .
git stash drop
```
**Os 58 arquivos staged devem ser preservados.** Ver a seção 2 — há um risco de perda de dados que você deve tratar antes de qualquer outra coisa.

---

## 1. CONTEXTO

**Produto:** Hermes OmniRoute Studio — edição desktop Windows do Hermes Agent (Nous Research), com roteamento local via OmniRoute, 106 ferramentas MCP, Product Studio, memória entre chats, Goal spec-first, preview de projeto, SSH, guardrails, cron e pt-BR.

**Caminho do projeto:** `C:\Users\zodyp\Documents\Codex\Hermes-OmniRoute`
**Aplicativo instalado:** `C:\Users\zodyp\AppData\Local\Programs\HermesOmniRoute`
**Pacote OmniRoute:** `%APPDATA%\npm\node_modules\omniroute` (versão 3.8.49)

**Origem deste documento:** auditoria forense independente executada em 2026-08-21. Os artefatos completos estão em `audit/`:
```text
audit/HERMES_OMNIROUTE_AUDIT.md              resumo executivo + inventário 58/58
audit/HERMES_OMNIROUTE_FINDINGS.md           41 findings detalhados com evidência
audit/HERMES_OMNIROUTE_ARCHITECTURE.md       arquitetura real + trust boundaries
audit/HERMES_OMNIROUTE_MCP_MATRIX.md         106 ferramentas, escopos, risco
audit/HERMES_OMNIROUTE_TEST_GAPS.md          o que os 1.549 testes não provam
audit/HERMES_OMNIROUTE_SECURITY.md           attack surface + cadeias de ataque
audit/HERMES_OMNIROUTE_UX.md                 UX, pt-BR, acessibilidade
audit/HERMES_OMNIROUTE_IMPROVEMENT_PLAN.md   melhorias classificadas
audit/_raw/staged.diff                       o diff staged integral (backup)
```

**Limite de prova do auditor — leia com atenção:** a auditoria rodou de um ambiente Linux com acesso somente-arquivo à máquina Windows do usuário. Portanto **não foram executados**: `typecheck`, `lint`, os 1.549 testes Electron, `build`, `NSIS`, o aplicativo instalado, o servidor MCP vivo, nem qualquer medição de performance. Os números reportados pelo usuário (1.549 PASS / 12 skip / build OK) **não foram confirmados** e você deve reconfirmá-los você mesmo, na máquina real, antes de aceitar qualquer premissa.

O que **foi** provado por execução: seis bypasses do plugin `dz23-guardrail`, rodando o próprio código Python. Os outputs estão reproduzidos nos findings.

---

## 2. AÇÃO ZERO — FAÇA ISTO ANTES DE QUALQUER OUTRA COISA

**FINDING HERMES-041.** Estado atual do Git:
```text
remote origin  https://github.com/NousResearch/hermes-agent.git
branch         feature/hermes-omniroute-studio
HEAD           e30388e (grafted — clone raso, 1 commit)
main           e30388e [origin/main]
commits locais 0
staged         58 arquivos, +3192 / -189
unstaged       0
```

As 3.192 linhas do trabalho OmniRoute existem **apenas no índice do Git**. Não há commit, não há histórico, o clone é raso. Um `reset`, um `checkout`, uma corrupção de índice ou um `gc` destrói tudo, e não há reflog para recuperar.

Execute, nesta ordem:
```powershell
cd C:\Users\zodyp\Documents\Codex\Hermes-OmniRoute
git bundle create ..\hermes-omniroute-backup-$(Get-Date -Format yyyyMMdd-HHmmss).bundle --all
git diff --cached > ..\hermes-omniroute-staged-$(Get-Date -Format yyyyMMdd-HHmmss).diff
git status --porcelain=v1 > ..\hermes-omniroute-status.txt
```
Confirme que o `.diff` tem ~199 KB e 4.664 linhas. Só então prossiga.

Depois disso, **peça autorização ao usuário** para criar um commit local (sem push) na branch de feature, para que o trabalho pare de existir só no índice. Se ele autorizar, faça. Se não, continue trabalhando com o backup em mãos e **nunca** execute um comando que mexa no índice.

---

## 3. ARQUITETURA REAL (resumida — detalhe em `audit/HERMES_OMNIROUTE_ARCHITECTURE.md`)

```text
Electron Main (main.ts, 15.2k linhas, 165 canais IPC)
  ↓ preload.ts — contextBridge, API nominal, contextIsolation+sandbox
Renderer React (SEM CSP, webviewTag:true, sem will-attach-webview)
  ↓ hermes:api → HTTP/WS local
Backend Python (gateway/ agent/ tools/ hermes_cli/ plugins/)
  ├─ tools: terminal (PTY) · execute_code (subprocesso RPC) · file_tools · ssh
  ├─ approvals: hardline floor → deny do usuário → yolo/off → allowlist → smart(LLM) → humano
  ├─ plugins: dz23-guardrail (INERTE — HERMES-001)
  ├─ delegação: max_spawn_depth 2, max_concurrent_children 5
  └─ MCP client → node integrations/omniroute-mcp-bridge.mjs
       ↓ import() de TS via tsx a partir de env var (HERMES-002)
     OmniRoute MCP server 3.8.49 — 106 ferramentas, escopos auto-concedidos (HERMES-003)
       ↓
     OmniRoute gateway http://127.0.0.1:20128 (sem auth, sem identidade — HERMES-016)
```

**Trust boundaries com problema:** renderer→main (sem validação de origem do sender), modelo→MCP (escopos auto-concedidos), conteúdo externo→agente (sem marcação de proveniência), Studio→runtime Hermes original (escrita direta).

---

## 4. FINDINGS — O QUE VOCÊ VAI CORRIGIR

Os 41 findings estão detalhados em `audit/HERMES_OMNIROUTE_FINDINGS.md` com `FACT`/`HYPOTHESIS`, arquivo:linha, reprodução, evidência, correção recomendada e teste de regressão. Aqui está o índice por onda.

### P0 — CRITICAL (4)
| ID | Resumo | Arquivo principal |
|---|---|---|
| HERMES-001 | Plugin `dz23-guardrail` nunca carrega — todos os guardrails inertes | `plugins/dz23-guardrail/plugin.yaml`, `hermes_cli/plugins.py` |
| HERMES-002 | Bridge MCP executa código arbitrário de `OMNIROUTE_PACKAGE_ROOT` | `integrations/omniroute-mcp-bridge.mjs` |
| HERMES-003 | Escopos MCP auto-concedidos — `ENFORCE_SCOPES=true` não restringe nada | `main.ts:14432`, `<omniroute>/server.ts:97,225` |
| HERMES-004 | `openExternal('file://…')` + `fs:writeText` = renderer→execução local | `main.ts:1555`, `fs-ipc.ts:160` · *upstream* |

### P1 — HIGH (12)
`HERMES-005` denylist não cobre Windows (**provado**) · `HERMES-006` gate de verificação forjável com `echo` (**provado**) · `HERMES-007` bypass por caminho relativo (**provado**) · `HERMES-008` `cwd`/`/workspace` como raiz confiável (**provado**) · `HERMES-009` erro de I/O aborta o boot · `HERMES-010` Studio escreve no runtime do Hermes original · `HERMES-011` `npm/pip install` sem gate algum · `HERMES-012` caminho SSH real do Windows sem cobertura · `HERMES-013` sem CSP + `webviewTag` sem handler · `HERMES-014` `pre_tool_call` fail-open duplo · `HERMES-015` falha de plugin de segurança é só warning · `HERMES-016` endpoint OmniRoute sem auth nem identidade.

### P2 — MEDIUM (19)
`HERMES-017` pt-BR 15% · `HERMES-018` indicador de segurança estático · `HERMES-019` doc promete backup inexistente · `HERMES-020` `_redact` fail-open · `HERMES-021` preset sobrescreve config do usuário · `HERMES-022` 8 assertions viram no-op no Windows · `HERMES-023` testes que verificam Markdown · `HERMES-024` falsos positivos bloqueiam doc/SQL (**provado**) · `HERMES-025` divergência CLI×gateway no Goal · `HERMES-026` `rule_key` vira auto-aprovação por diretório · `HERMES-027` parse frágil da compressão · `HERMES-028` `pre_verify` é nudge com teto 3 · `HERMES-029` `curl` sem `--` · `HERMES-030` 12 skips, 11 identificáveis · `HERMES-031` `cost_usd` nunca chega · `HERMES-032` 106 vs 107 tools · `HERMES-033` proteção de `connection.json` não testada no Windows · `HERMES-034` `codesign` fail-open · `HERMES-035` health check com métricas grosseiras.

### P3 — LOW (6)
`HERMES-036` formatação misturada · `HERMES-037` mudança de path no-op · `HERMES-038` versão PE sem validação · `HERMES-039` `plugin.yaml` duplicado · `HERMES-040` alias sem acento · `HERMES-041` trabalho sem commit.

---

## 5. EVIDÊNCIA EXECUTADA — reproduza antes de corrigir

Rode isto e confirme que você vê o mesmo. Se não vir, marque `DISPUTED_FINDING` e apresente sua evidência.

```python
# python - <<'PY'   (a partir da raiz do repositório)
import importlib.util, os
from pathlib import Path
spec = importlib.util.spec_from_file_location('g','plugins/dz23-guardrail/__init__.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
os.environ['HERMES_GUARDRAIL_WORKSPACE_ROOTS'] = str(Path.cwd())

# HERMES-005 — denylist não cobre Windows
for c in ['del /s /q C:\\Users\\zodyp\\Documents','rd /s /q C:\\projeto',
          'Remove-Item -Recurse -Force C:\\Users\\zodyp','rm -r -f /tmp/x',
          'find . -delete','git clean -fdx','DROP DATABASE prod','TRUNCATE TABLE users',
          'docker volume prune -f','rm -rf /tmp/x']:
    r = m.on_pre_tool_call('terminal', {'command': c})
    print(('BLOQUEADO' if r and r.get('action')=='block' else 'PASSOU   '), c)

# HERMES-007 — caminho relativo
print(m.on_pre_tool_call('write_file', {'path':'../../../../etc/passwd'}))   # -> None

# HERMES-006 — gate forjável
s='x'
m.on_post_tool_call('write_file', {'path':'a.ts'}, {'ok':True}, 'success', s)
m.on_post_tool_call('terminal', {'command':'echo npm test'}, 'npm test', 'success', s)
print(m.on_pre_verify(session_id=s, coding=True, changed_paths=['a.ts']))     # -> None

# HERMES-024 — falso positivo
print(m.on_pre_tool_call('write_file', {'path':'doc.md','content':'Nunca rode rm -rf /'}))  # -> block
PY
```

Resultado esperado (o que o auditor obteve): apenas `rm -rf /tmp/x` bloqueia; o caminho relativo retorna `None`; `echo npm test` satisfaz o gate; a documentação é bloqueada.

Para HERMES-001, verifique:
```powershell
hermes plugins list        # dz23-guardrail deve aparecer enabled=False, erro "not enabled in config"
```

---

## 6. ORDEM DE EXECUÇÃO — WAVES

Cada wave só começa quando a anterior tiver critério de aceite cumprido e regressão verde.

### WAVE 0 — proteção e baseline
- **Arquivos:** nenhum do repositório.
- **Findings:** HERMES-041.
- **Mudanças:** bundle + diff de backup (seção 2). Depois, capturar o baseline **real** você mesmo: `typecheck`, `lint`, suíte Electron completa, suíte Python, build, NSIS, secret scan. Registre os números observados, **não** os reportados.
- **Critério de aceite:** backup verificado; baseline documentado em `audit/BASELINE_CODEX.md` com contagem exata de pass/fail/skip e a **lista nomeada dos skips**.
- **Risco de regressão:** nenhum.

### WAVE 1 — P0
- **Findings:** HERMES-001, 002, 003, 004.
- **Arquivos:** `plugins/dz23-guardrail/plugin.yaml`, `hermes_cli/plugins.py`, `integrations/omniroute-mcp-bridge.mjs`, `apps/desktop/electron/main.ts`, `apps/desktop/electron/fs-ipc.ts`, `apps/desktop/electron/hardening.ts`.
- **Mudanças:**
  1. `kind: backend` + `security_critical: true` no manifesto; runtime que **aborta** se um plugin `security_critical` não carregar; instalador que garante habilitação; UI que mostra o estado do guardrail.
  2. Bridge: allowlist de raízes, `realpath`, verificação de nome/versão do pacote, sem `tsx` em produção. Ignorar `OMNIROUTE_PACKAGE_ROOT` em build empacotado.
  3. Escopo MCP default mínimo (`read:health read:models read:combos read:quota read:usage execute:completions`); resto por consentimento explícito; **remover `write:plugins` do default**.
  4. `openExternalUrl`: confinar `file:` a raízes permitidas, aplicar `rejectSensitiveFilePath`, recusar extensões executáveis. `hermes:fs:*`: implementar a allowlist de raízes que o comentário em `fs-ipc.ts:156-159` já promete, e corrigir o comentário.
- **Critério de aceite:** os 4 testes de regressão da seção 7 passam; `hermes plugins list` mostra o guardrail ativo; `plugin_install` via MCP é negado por escopo no default.
- **Risco de regressão:** ALTO em `main.ts` (arquivo enorme). Faça mudanças cirúrgicas, uma por vez, com a suíte Electron rodando entre cada uma.

### WAVE 2 — P1
- **Findings:** HERMES-005 a 016.
- **Mudanças-chave:**
  - Guardrail reescrito: denylist por plataforma usando o parser real do core (`tools/approval.py:_command_detection_variants`), casamento **só** em `_command_text` (nunca no JSON completo), resolução de caminho contra a raiz da sessão via `agent/runtime_cwd.resolve_agent_cwd()`, remoção de `/workspace` fixo, gate de verificação baseado em **exit code real** com `echo`/`printf`/`cat` na denylist de comandos de verificação e `pytest`/`tox`/`nox` adicionados aos runners.
  - `installBundled*` em try/catch por bundle, com estado consultável e exibido na UI.
  - Namespace `HERMES_HOME/omniroute-studio/` em vez de escrever em `ACTIVE_HERMES_ROOT`.
  - Padrão de detecção para instaladores de pacote + OSV para todo install + `--ignore-scripts` por default.
  - Suíte SSH parametrizada por `mux: [true,false]`.
  - CSP via `onHeadersReceived` + `will-attach-webview` + `web-contents-created`.
  - `security_critical` fail-closed nos hooks.
  - Token local + verificação de identidade para o endpoint 20128.
- **Critério de aceite:** o script da seção 5 passa a mostrar **bloqueado** para os 10 comandos destrutivos, **aprovação exigida** para o caminho relativo, **não verificado** para `echo npm test`, e **não bloqueado** para a documentação.

### WAVE 3 — arquitetura e integridade
- **Findings:** HERMES-010 (conclusão), HERMES-019, HERMES-026.
- Backup timestamped real na instalação de bundles; desinstalação que reverte; `rule_key` com namespace forçado e granularidade por arquivo.

### WAVE 4 — integrações
- **Findings:** HERMES-021, 025, 027, 031, 032, 035.
- Preset que preenche sem clobber; função única de gate do Goal para CLI e gateway; protocolo da bridge com delimitador explícito; `cost_usd` no payload do hook; contagem de tools gerada em build; constante única do endpoint.

### WAVE 5 — segurança
- **Findings:** HERMES-020, 029, 033, 034.
- `_redact` fail-closed; `--` no `curl` + allowlist de esquema; ACL Windows para `connection.json` com verificação de leitura de volta; `codesign` que aborta em vez de re-assinar; branch de update fora do controle do renderer.

### WAVE 6 — reliability e recovery
- **Findings:** HERMES-028 + Parte A7 do plano de melhoria.
- Modo `verify.strict`; cancelamento propagado a delegados; timeout por delegado com `PARTIAL` honesto; circuit breaker por provedor; teto de custo por sessão que o agente não pode desligar.
- **Injeção de falha obrigatória:** MCP indisponível, tool retorna erro, timeout, rede cai, preview morre, SSH falha, memória indisponível, config corrompida, porta ocupada, restart no meio da operação. Para cada uma, o sistema deve reportar `FAILED` ou `BLOCKED` — **nunca** sucesso aparente.

### WAVE 7 — testes
- **Findings:** HERMES-022, 023, 030.
- Converter os 8 `if (process.platform …)` em `test.skipIf` e escrever o equivalente Windows; reduzir o teste da skill a smoke de schema; runner que imprime a lista nomeada de skips; **implementar todos os testes da seção 7**.
- **Critério de aceite:** nenhum teste contém `process.platform` no corpo; a suíte imprime skips nomeados; a divergência de HERMES-030 fica resolvida com o número real.

### WAVE 8 — performance
- Medir e registrar de verdade (o auditor não pôde): `COLD_START`, `WARM_START`, `IDLE_RAM`, `ACTIVE_RAM`, `IDLE_CPU`, `ACTIVE_CPU`, `PROCESS_COUNT`, `MCP_LATENCY`, `PREVIEW_START_TIME`, `SHUTDOWN_TIME`. Procurar crescimento progressivo de memória em 30 min de uso e processos órfãos após shutdown.

### WAVE 9 — UI/UX
- **Findings:** HERMES-017, 018 + Parte B do plano de melhoria.
- pt-BR ≥90% com teste de cobertura (aprovações e segurança primeiro); chip de acesso do agente vinculado a estado real e visível em toda largura; **catálogo de presets de provedor com base URL pré-preenchida** (B1); **Sign in with OpenRouter via OAuth PKCE** reusando `native-oauth.ts` + `native-token-store.ts` (B2); painel principal estilo Qoder/Quest com o escopo delimitado em B3.
- **Restrições:** reutilizar os primitivos de UI existentes; nenhuma biblioteca nova; nenhuma mudança em `main.ts` nesta wave.
- **Proibido:** implementar login de assinatura Claude ou ChatGPT por cookie/automação de sessão web. Ver B2 — é circumvention, quebra sozinho e leva a banimento de conta.

### WAVE 10 — packaging e installer
- Instalação limpa, upgrade sobre a versão anterior, reinstalação, atalhos, diretórios, dados persistentes, desinstalação, arquivos residuais, permissões, comportamento com o app aberto, rollback após falha.
- **Não desinstale a instalação principal do usuário.** Use uma VM ou um usuário Windows separado.

### WAVE 11 — regressão completa
Rode tudo da seção 8.

### WAVE 12 — revisão final
Teste o aplicativo real (seção 9), faça a revisão adversarial (seção 10), e produza o relatório final.

---

## 7. TESTES DE REGRESSÃO OBRIGATÓRIOS

Escreva estes. Cada um deve falhar no código atual e passar depois da correção.

**Wave 1**
1. `test_guardrail_loads_through_real_plugin_manager` — sobe `PluginManager` com o `config.yaml` que o instalador produz; assere `dz23-guardrail` habilitado e `pre_tool_call` invocado numa chamada real. **Proibido usar `importlib.spec_from_file_location`.**
2. `test_security_critical_plugin_failure_aborts_start` — plugin `security_critical` com import quebrado → start falha com mensagem acionável.
3. `test_bridge_rejects_root_outside_allowlist` — `OMNIROUTE_PACKAGE_ROOT` para diretório temporário válido → recusa, não importa nada dele.
4. `test_mcp_default_scopes_deny_plugin_install` — escopo default + `plugin_install` → `isError` com `missing_scopes`; e o default **não contém** `write:plugins`.
5. `test_open_external_rejects_executable_and_sensitive_paths` — `.exe`, `.bat`, `~/.ssh/id_rsa` → recusados.
6. `test_fs_write_confined_to_allowed_roots` — escrita fora das raízes → recusada.

**Wave 2**
7. `test_destructive_denylist_covers_windows` — tabela com os 10 comandos da seção 5 (devem bloquear) + negativos (`git clean -n`, doc citando `rm -rf`) que não devem.
8. `test_workspace_gate_resolves_relative_and_symlink` — `..`, `..\`, junction, UNC, `~`.
9. `test_workspace_gate_ignores_process_cwd` — processo lançado de `C:\` → escrita em `C:\Windows\…` ainda exige aprovação.
10. `test_verification_requires_real_exit_code` — exit≠0 sem "error" → não verifica; `echo npm test` → não verifica; `pytest` exit 0 → verifica; sem `exit_code` → não verifica.
11. `test_guardrail_does_not_block_file_content` — conteúdo com `rm -rf` e `DROP TABLE` → não bloqueia.
12. `test_bundle_install_failure_does_not_break_boot` — `fs` que lança → boot continua, estado reporta `failed`.
13. `test_studio_never_writes_into_active_hermes_root`.
14. `test_package_install_requires_approval` — `npm install left-pad` sem lockfile → aprovação; `npm ci` com lockfile → auto.
15. SSH parametrizado por `mux: [true,false]`.
16. `test_csp_header_present` e `test_webview_attributes_neutralized`.
17. `test_omniroute_endpoint_requires_local_token`.

**Waves 3–5**
18. `test_managed_bundle_creates_timestamped_backup`.
19. `test_redact_unavailable_writes_no_report`.
20. `test_preset_preserves_user_max_turns_and_approval_mode`.
21. `test_cli_goal_draft_pauses_like_gateway` e `test_pause_failure_does_not_claim_paused`.
22. `test_connection_json_acl_on_windows` — lê a ACL de volta.
23. `test_curl_argv_has_separator_and_scheme_allowlist`.

**Wave 9**
24. `test_locale_coverage_threshold` — percorre `Translations` recursivamente, compara chaves de cada locale com `en`, falha abaixo de 90% para locales anunciados.
25. `test_agent_access_chip_reflects_state` — acesso desligado → texto não diz "ativo".

---

## 8. GATE DE CORREÇÃO — execute tudo, na máquina Windows real

```text
typecheck
lint
unit
integration
Electron tests
security tests
MCP tests
agent tests
memory tests
Goal tests
Product Studio tests
Preview tests
SSH safety tests
guardrail tests
cron tests
build
NSIS
secret scan
dependency/security scan
runtime smoke
UI smoke
```
Mais **todos** os testes novos da seção 7.

Regra: nenhum gate pode ser declarado `PASS` sem o output do comando anexado ao relatório.

---

## 9. TESTE DO APLICATIVO REAL — o pipeline verde não encerra a tarefa

Abra o aplicativo resultante e exercite:
```text
startup · onboarding · navigation · Product Studio · Memory · Agents · Goal
MCP · Preview · SSH · Caveman · Guardrails · Cron · pt-BR · settings
restart · shutdown · error recovery
```
E inspecione:
```text
console · network · Electron logs · processos · uncaught exceptions · unhandled rejections
```
Critérios que o auditor não pôde verificar e que você deve verificar:
- O guardrail aparece como **ativo** na UI e realmente bloqueia `del /s /q` numa sessão real.
- `omniroute_tool_search` ou o endpoint de status do MCP reporta a contagem real de ferramentas — resolva a divergência 106 × 107 com o número vivo.
- Nenhum processo órfão após fechar o app (preview, node da bridge, PTY).
- Trocar o idioma para pt-BR e navegar por todas as telas anotando o que ainda aparece em inglês.
- Zero unhandled rejections no log em um ciclo completo de uso.

---

## 10. REGRESSION LOOP

```text
IMPLEMENT
↓
TEST
↓
INSPECT
↓
FIND REGRESSION
↓
FIX ROOT CAUSE
↓
RETEST
```
Repita até não existirem falhas internas conhecidas corrigíveis dentro do escopo. **Não existe limite artificial de uma rodada.**

Ao final de cada wave, faça a pergunta adversarial: *se eu quisesse quebrar isto agora, qual caminho eu tentaria?* Se encontrar algo novo, registre como finding e trate.

---

## 11. VOCÊ ESTÁ AUTORIZADO A

Investigar, editar, refatorar, criar testes, corrigir frontend, backend/local services, Electron, IPC, MCP, agentes, memória, Product Studio, Goal, Preview, SSH, Caveman, guardrails, cron, instalador; melhorar UI/UX e performance; corrigir vulnerabilidades.

**Desde que:** preserve funcionalidades válidas, trate a causa raiz e não reduza a cobertura de teste.

---

## 12. O QUE NÃO DEVE SER REMOVIDO OU ENFRAQUECIDO

Isto funciona e é bom. Não toque, exceto para fortalecer:

- `contextIsolation: true`, `sandbox: true`, `nodeIntegration: false` em todas as janelas.
- `setWindowOpenHandler` com `action: 'deny'` incondicional.
- Preload com API nominal, **sem** passthrough genérico de canal.
- `execFile` com argv em array em todo o código git/gh/ssh; ausência de `shell: true`.
- `resolveReadableFileForIpc` + `rejectSensitiveFilePath`.
- CDP fechado em build empacotado.
- `safeStorage` para tokens.
- **Hardline floor** aplicado antes do bypass `--yolo` (`tools/approval.py:4365-4368`) e sua detecção resistente a ofuscação.
- Isolamento de canal do `_smart_approve` (política do operador no system, comando em `<command>`).
- `execute_code` em subprocesso com RPC autenticado.
- Gate não-bypassável de escrita em `AGENTS.md`/`CLAUDE.md`/`.cursorrules`.
- `request_tool_approval` fail-closed sem humano.
- Identidade lado-a-lado do Studio: `appId`, `executableName`, protocolo `hermes-omniroute`, `artifactName`, versão PE, `test-desktop.mjs` parametrizado.
- O teste `test_gateway_goal_draft_pauses_for_real_spec_review` — é um bom teste, assere estado real.
- As skills do Product Studio como **documentação de processo**. Elas são bem escritas. Só não as trate como controle executável.

---

## 13. DEPENDÊNCIAS EXTERNAS

Se uma correção não puder ser comprovada por falta de credencial, hardware, serviço, permissão, servidor ou API externa, registre:
```text
BLOCKED_BY_EXTERNAL_DEPENDENCY
dependency=
affected_feature=
what_was_verified=
what_could_not_be_verified=
exact_requirement_to_unblock=
```
**Não utilize mocks para converter esse estado em PASS.**

Casos já conhecidos: teste live de SSH (`HERMES_WIN_SSH_HOST/USER/HERMES`) — resolva com um container OpenSSH efêmero em CI em vez de deixar pulado para sempre; provedores de modelo que exigem chave do usuário.

---

## 14. NÃO CONFIE CEGAMENTE NESTE RELATÓRIO

> Os findings do Claude são hipóteses técnicas de alta prioridade, não verdade absoluta.

Reproduza cada problema antes de corrigir, quando tecnicamente possível. A seção 5 traz o script exato para os seis achados provados por execução.

Se discordar de um finding, registre:
```text
DISPUTED_FINDING
id=
motivo=
evidência=
```
e **não implemente uma correção incorreta apenas porque o relatório mandou.**

Pontos onde o auditor foi explícito sobre incerteza e que merecem sua verificação independente:
- **HERMES-001** é a conclusão mais consequente de toda a auditoria e foi derivada estaticamente da cadeia do loader. Confirme com `hermes plugins list` na máquina real **antes** de reescrever o manifesto.
- **HERMES-030**: 11 de 12 skips identificados. O 12º precisa do output real da suíte.
- **HERMES-032**: 106 vs 107 tools. Resolva com `tools/list` contra o servidor vivo.
- **HERMES-004** e **HERMES-013**: as primitivas são FATO; a cadeia de exploração é HYPOTHESIS. Valide antes de dimensionar o esforço.
- Tudo marcado `ORIGEM: upstream` (HERMES-004, 013, 029, 034) é herdado do Hermes Agent. Decida com o usuário se corrige localmente, propõe upstream, ou aceita com registro de risco — mas **decida explicitamente**, não ignore.

---

## 15. COMPORTAMENTO ESPERADO AO FINAL

```text
1. Os 58 arquivos staged continuam staged, com backup verificado.
2. Nenhum commit e nenhum push sem autorização explícita do usuário.
3. O plugin dz23-guardrail carrega de verdade e é visível na UI como ativo.
4. Comandos destrutivos do Windows são bloqueados; documentação e SQL legítimos não são.
5. O gate de verificação exige exit code real e não pode ser satisfeito por echo.
6. Escrita fora do workspace exige aprovação, inclusive por caminho relativo e symlink.
7. O escopo MCP default não inclui write:plugins; ativação é consciente e revogável.
8. A bridge MCP não carrega código de caminho não confiável.
9. O renderer não alcança execução local por file:// nem por <webview>.
10. O Studio não escreve no runtime do Hermes original.
11. npm/pip install passam por gate com verificação de advisory.
12. pt-BR ≥90%, com aprovações e mensagens de segurança traduzidas primeiro.
13. Login por OAuth PKCE (OpenRouter) funciona; base URLs vêm pré-preenchidas.
14. Nenhum teste contém process.platform no corpo; os skips são nomeados no relatório.
15. Todos os gates da seção 8 executados na máquina Windows real, com output anexado.
16. O aplicativo instalado exercitado de ponta a ponta, sem processos órfãos e sem
    unhandled rejections.
17. Um relatório final que separa PASS real de BLOCKED_BY_EXTERNAL_DEPENDENCY, sem
    converter um no outro.
```

---

## 16. LEMBRETE FINAL

Este produto passou em 1.549 testes enquanto seu plugin de segurança não carregava e seus três gates eram contornáveis por `del /s /q`, por `../` e por `echo`. **Teste passando não é funcionalidade.** Seu trabalho não é deixar o pipeline verde — é fazer o produto ser o que a documentação dele afirma que ele é.
