# HERMES OMNIROUTE — AUDITORIA FINAL

Auditor: Claude (independente) · Data: 2026-08-21 · Projeto: `C:\Users\you\Documents\Codex\Hermes-OmniRoute`

```text
HERMES OMNIROUTE — AUDITORIA FINAL

VERDICT=REQUIRES_CORRECTIONS
CONFIDENCE_LEVEL=ALTA para código/estático e para os testes que executei; BAIXA para runtime do app instalado (não executável deste ambiente)
P0_CRITICAL=4
P1_HIGH=12
P2_MEDIUM=19
P3_LOW=6

STAGED_FILES_EXPECTED=58
STAGED_FILES_REVIEWED=58
STAGED_FILES_NOT_REVIEWED=0

ELECTRON_TESTS_EXPECTED=1549
ELECTRON_TESTS_PASS=NOT_TESTED
ELECTRON_TESTS_FAIL=NOT_TESTED
ELECTRON_TESTS_SKIPPED=NOT_TESTED
SKIPPED_TESTS_REVIEWED=11/12 (12º não identificável estaticamente — ver HERMES-030)

TYPECHECK=NOT_TESTED
LINT=NOT_TESTED
UNIT_TESTS=PARTIAL (executei os testes do plugin dz23-guardrail manualmente e provei 6 bypasses)
INTEGRATION_TESTS=NOT_TESTED
ELECTRON_TESTS=BLOCKED_BY_EXTERNAL_DEPENDENCY (exige toolchain Windows)
BUILD=NOT_TESTED
NSIS=NOT_TESTED
SECRET_SCAN=PASS (nos 58 arquivos staged; nenhum literal de credencial encontrado)
DEPENDENCY_AUDIT=PARTIAL

APPLICATION_RUNTIME_TESTED=NOT_TESTED
INSTALLED_APPLICATION_TESTED=NOT_TESTED
DEVTOOLS_INSPECTED=NOT_TESTED
LOGS_INSPECTED=NOT_TESTED

MCP_TOOLS_EXPECTED=107
MCP_TOOLS_DISCOVERED=106 (enumeração estática do pacote omniroute 3.8.49)
MCP_PASS=0
MCP_PARTIAL=0
MCP_FAIL=0
MCP_BLOCKED=0
MCP_NOT_TESTED=106 (nenhuma chamada viva executada — servidor não iniciado neste ambiente)

PRODUCT_STUDIO=PARTIAL
MEMORY=PARTIAL
AGENTS=PARTIAL
GOAL=PARTIAL
PT_BR=FAIL
PREVIEW=NOT_TESTED
SSH=PARTIAL
CAVEMAN=PARTIAL
GUARDRAILS=FAIL
CRON=NOT_TESTED

ELECTRON_SECURITY=PARTIAL
IPC_SECURITY=PARTIAL
MCP_SECURITY=FAIL
PROMPT_INJECTION_RESISTANCE=FAIL
FILESYSTEM_SECURITY=FAIL
SHELL_SECURITY=PARTIAL
SSH_SECURITY=PARTIAL
SECRET_HANDLING=PARTIAL
PERFORMANCE=NOT_MEASURED
ACCESSIBILITY=NOT_TESTED
UI_UX=PARTIAL
RECOVERY=PARTIAL
INSTALLER=NOT_TESTED
UPGRADE_PATH=PARTIAL

READY_FOR_CODEX_FIX_PHASE=YES
READY_FOR_COMMIT=NO
READY_FOR_PUSH=NO
READY_FOR_RELEASE=NO
```

---

## Limite de prova declarado (leia antes de qualquer conclusão)

Esta auditoria rodou de um container Linux em nuvem com as pastas do usuário montadas via bridge somente-arquivo. Isso define exatamente o que é FATO e o que é `NOT_TESTED`:

**Foi possível (evidência direta):**
- Estado Git completo, diff staged integral (4.664 linhas), inventário 58/58.
- Leitura integral do código Electron/React/Python relevante.
- **Execução real do plugin `dz23-guardrail`** em Python — 6 bypasses provados com output.
- Enumeração estática do pacote `omniroute@3.8.49` instalado (`%APPDATA%\npm\node_modules\omniroute`), incluindo `server.ts`, `scopeEnforcement.ts` e todas as coleções de ferramentas.
- Scan de segredos nos arquivos staged.

**Não foi possível (e por quê):**
- `device_bash` roda numa **VM Linux**, não no Windows do usuário. Toolchain Windows, Electron, `vitest` da suíte desktop, `electron-builder`, NSIS e o `.exe` instalado são inalcançáveis daqui.
- Consequência: `typecheck`, `lint`, os 1.549 testes Electron, `build`, `NSIS`, runtime do app, DevTools, processos, RAM/CPU, preview, cron e chamadas MCP vivas ficam `NOT_TESTED`.
- **Os números fornecidos pelo usuário (1.549 PASS / 12 skip / typecheck / build / NSIS) NÃO foram confirmados.** Foram tratados como afirmação não verificada, conforme a missão exige.

Isso não enfraquece os achados abaixo: os achados P0/P1 são de código e configuração, não de runtime, e vários foram provados por execução.

---

## Veredito em uma frase

O Hermes OmniRoute Studio é um trabalho de integração competente e bem documentado, mas **a camada de segurança que ele anuncia — guardrails determinísticos, gate de verificação, escopos MCP — não funciona**: o plugin de guardrail muito provavelmente nunca carrega, e mesmo se carregasse seus três gates são contornáveis por caminhos triviais que eu executei e comprovei. O produto passa nos testes atuais porque os testes testam a documentação e o caminho feliz, não a propriedade de segurança.

---

## 2 — Resposta ao objetivo da auditoria

> *O Hermes OmniRoute Studio modificado está realmente correto, seguro, integrado, estável, utilizável e melhor que a base original, ou apenas passa nos testes atualmente existentes?*

**Correto:** parcialmente. A engenharia de empacotamento e identidade lado-a-lado (appId, executável, protocolo, NSIS, rcedit, `test-desktop.mjs` parametrizado) está bem feita e é a parte mais sólida do stage.

**Seguro:** não. Quatro P0 e doze P1, dos quais seis foram provados por execução. A palavra "guardrail" aparece 20+ vezes na documentação e o mecanismo correspondente está inerte.

**Integrado:** parcialmente e de forma invasiva. O Studio escreve plugin, bridge e script dentro de `ACTIVE_HERMES_ROOT` — o runtime do **Hermes original** — contrariando a premissa "Hermes original preservado".

**Estável:** risco relevante. Os quatro `installBundled*` rodam sem `try/catch` dentro de `app.whenReady().then()`; um erro de filesystem aborta o restante do callback e o app não abre janela.

**Utilizável:** para um usuário brasileiro leigo — que é o público declarado em `docs/hermes-omniroute-studio.md` — não. O catálogo pt-BR cobre **~15%** das chaves de tradução (≈380 de ≈2.452). Os outros idiomas cobrem 79–107%.

**Melhor que a base original:** em identidade de produto, roteamento e documentação, sim. Em postura de segurança, **não** — o Studio adiciona superfície (bridge que executa TS arbitrário, 106 ferramentas MCP com escopos auto-concedidos, aprovações relaxadas para `smart`) sem adicionar contenção efetiva.

**Ou apenas passa nos testes?** Predominantemente isto. Ver `HERMES_OMNIROUTE_TEST_GAPS.md`.

---

## 3 — Preservação do Hermes original (FATO)

```text
remote origin       https://github.com/NousResearch/hermes-agent.git
branch atual        feature/hermes-omniroute-studio
HEAD                e30388e (grafted)
main                e30388e [origin/main]
commits locais      0
unstaged (tracked)  0
staged              58 arquivos, +3192 / -189
```

**Fatos que merecem atenção imediata:**

1. **Zero commits locais.** `feature/hermes-omniroute-studio` aponta exatamente para `origin/main`. Todo o trabalho do OmniRoute existe **apenas no índice do Git** — não há commit, não há reflog, não há backup. Um `git reset`, um `git checkout`, um crash do disco ou um `git stash` mal dado destrói 3.192 linhas irrecuperavelmente. **Este é o risco operacional número um do projeto agora** (HERMES-041).
2. **Clone raso (`grafted`).** Não há histórico para comparar contra o upstream real; `git log` tem um único commit. Bisect, blame e diff histórico estão indisponíveis.
3. **O Hermes original NÃO está preservado em runtime.** `main.ts:15079-15110` grava, a cada start empacotado, dentro de `ACTIVE_HERMES_ROOT` (= `HERMES_HOME/hermes-agent`, o runtime compartilhado):
   - `plugins/dz23-guardrail/` (código Python executável),
   - `integrations/omniroute-mcp-bridge.mjs`.
   A separação conquistada no nível de aplicação (appId/exe/protocolo) é desfeita no nível de runtime. Ver HERMES-010.

---

## 4 — Inventário dos 58 arquivos staged

```text
EXPECTED_STAGED_FILES=58
ACTUAL_STAGED_FILES=58
DIVERGENCE=nenhuma
```

Legenda de Status: `OK` sem achado · `OBS` observação sem finding · `FINDING` gera achado.

```text
STAGED FILE AUDIT

01/58 — NOTICE-OMNIROUTE-STUDIO.md
Objetivo: aviso de obra derivada (MIT do Hermes preservado), identidade do Studio.
Alteração: novo, 16 linhas.
Risco: baixo. Afirma "bridge local allowlisted" — a allowlist cobre só os args `--compression-*`, não a origem do código carregado.
Cobertura: nenhuma.
Finding relacionado: HERMES-002 (overclaim).
Status: OBS

02/58 — README.md
Objetivo: banner do fork.
Alteração: +2 linhas.
Risco: nenhum. Anuncia "107 MCP tools" — enumerei 106.
Finding relacionado: HERMES-032.
Status: OBS

03/58 — apps/desktop/electron/bundled-product-studio.test.ts
Objetivo: testar instalação dos bundles gerenciados.
Alteração: novo, 125 linhas, 6 testes.
Risco: médio — nenhum teste cobre falha de I/O (EPERM/EACCES/disco cheio), que é exatamente o modo de falha que derruba o boot.
Cobertura: caminho feliz + `skipped-unmanaged`.
Finding relacionado: HERMES-009.
Status: FINDING

04/58 — apps/desktop/electron/bundled-product-studio.ts
Objetivo: copiar skill, guardrail, bridge e health script para o disco do usuário com marcador de propriedade.
Alteração: novo, 120 linhas.
Risco: ALTO — sem backup (a doc promete backup timestamped), sem `try/catch`, destino é o runtime do Hermes original.
Cobertura: 6 testes, nenhum de falha.
Finding relacionado: HERMES-009, HERMES-010, HERMES-019.
Status: FINDING

05/58 — apps/desktop/electron/desktop-installation.test.ts
Objetivo: id de instalação persistente.
Alteração: assertion de modo 0600 envolvida em `if (process.platform !== 'win32')`.
Risco: MÉDIO — no Windows o teste **passa sem asserir nada**. Não reporta skip.
Finding relacionado: HERMES-022, HERMES-033.
Status: FINDING

06/58 — apps/desktop/electron/desktop-uninstall.test.ts
Objetivo: reconhecer o diretório de instalação lado-a-lado.
Alteração: +1 teste.
Risco: baixo. Teste correto e específico.
Status: OK

07/58 — apps/desktop/electron/desktop-uninstall.ts
Objetivo: `resolveRemovableAppPath` aceita `Hermes OmniRoute Studio`.
Alteração: +1 alternativa no regex.
Risco: baixo. Coberto pelo teste 06.
Status: OK

08/58 — apps/desktop/electron/git-worktree-ops.test.ts
Objetivo: tolerar EPERM do Git for Windows no cleanup de temp.
Alteração: helper `removeTemporaryDirectory` + retries.
Risco: baixo — o try/catch é restrito a `win32 && EPERM`, corretamente.
Status: OK

09/58 — apps/desktop/electron/hardening.test.ts
Objetivo: adaptar testes POSIX de permissão ao Windows.
Alteração: `posixTest = win32 ? test.skip : test` aplicado a 7 testes.
Risco: ALTO — os 7 testes que provam que `connection.json` (que contém o token remoto) é owner-only são **pulados justamente no Windows**, a única plataforma de release. A proteção real no Windows não tem nenhuma verificação equivalente.
Finding relacionado: HERMES-033.
Status: FINDING

10/58 — apps/desktop/electron/hardening.ts
Objetivo: injetar `getuid` para testabilidade.
Alteração: +`options.getuid`.
Risco: baixo. Mudança correta e mínima.
Status: OK

11/58 — apps/desktop/electron/main.ts
Objetivo: identidade do Studio, IPC de compressão, IPC de config MCP, instalação dos bundles no boot.
Alteração: +149 linhas.
Risco: CRÍTICO — `omniRouteMcpBridgePath()` inclui `process.cwd()` como candidato; `omniRouteMcpNodeCommand()` cai em `where.exe node` e depois no literal `'node'`; os quatro `installBundled*` rodam sem try/catch no `whenReady`.
Cobertura: os handlers IPC novos não têm teste de integração; só as funções puras têm.
Finding relacionado: HERMES-002, HERMES-009, HERMES-010.
Status: FINDING

12/58 — apps/desktop/electron/omniroute-compression.test.ts
Objetivo: testar parse/allowlist da compressão.
Alteração: novo, 49 linhas, 4 testes.
Risco: médio — nenhum teste de stdout malformado, timeout ou processo morto.
Finding relacionado: HERMES-027.
Status: FINDING

13/58 — apps/desktop/electron/omniroute-compression.ts
Objetivo: controlar Caveman via CLI da bridge.
Alteração: novo, 113 linhas.
Risco: médio — `parseCompressionStatus` usa heurística `lastIndexOf('\n{')` e `JSON.parse` sem try/catch; allowlist de modo está correta; verifica o estado após o set (bom).
Finding relacionado: HERMES-027.
Status: FINDING

14/58 — apps/desktop/electron/preload.ts
Objetivo: expor `omniRouteCompression` e `omniRouteMcp`.
Alteração: +7 linhas, funções nomeadas (sem canal dinâmico).
Risco: baixo em si; `omniRouteMcp.getConfig()` vaza para o renderer o caminho absoluto do node e do bridge.
Status: OBS

15/58 — apps/desktop/electron/ssh-config.test.ts
Objetivo: tornar os paths dos testes independentes de plataforma.
Alteração: `path.join`/`path.resolve` no lugar de literais POSIX.
Risco: baixo. Adaptação legítima.
Status: OK

16/58 — apps/desktop/electron/ssh-connection.test.ts
Objetivo: fazer os testes de SSH passarem no Windows.
Alteração: `mux: true` injetado em 9 construtores + `return` antecipado no teste de symlink em win32.
Risco: ALTO — `mux: true` foi adicionado porque no Windows o default é outro. Os testes agora exercitam o caminho multiplexado que **não é o que roda no Windows**. O caminho real de produção ficou sem cobertura, e o `return` em win32 faz um teste de segurança reportar PASS sem asserir.
Finding relacionado: HERMES-012, HERMES-022.
Status: FINDING

17/58 — apps/desktop/electron/windows-hermes-path.ts
Objetivo: usar regras de path do alvo, não do host.
Alteração: `path.win32.join` / `path.posix.join`.
Risco: baixo — em Windows real é no-op; muda comportamento só em cenário cross-platform de teste.
Finding relacionado: HERMES-037.
Status: OBS

18/58 — apps/desktop/index.html
Objetivo: título da janela.
Alteração: 1 linha.
Risco: nenhum. **Observação relevante: este arquivo não define CSP** — e nenhuma CSP é aplicada no processo main.
Finding relacionado: HERMES-013.
Status: OBS

19/58 — apps/desktop/package.json
Objetivo: identidade completa do Studio + extraResources dos bundles.
Alteração: +60/-24.
Risco: baixo-médio. `"name": "hermes"` permanece; `extraResources` copia diretórios inteiros (pode carregar `__pycache__`).
Status: OBS

20/58 — apps/desktop/scripts/set-exe-identity.mjs
Objetivo: carimbar versão PE de 4 partes e identidade DZ23.
Alteração: +`normalizeWindowsVersion`.
Risco: baixo — `parseInt(...)||0` engole parte inválida; sem clamp em 65535.
Finding relacionado: HERMES-038.
Status: OBS

21/58 — apps/desktop/scripts/set-exe-identity.test.mjs
Objetivo: testar a normalização.
Alteração: novo, 2 testes.
Risco: baixo. Testes corretos; faltam casos de overflow.
Status: OK

22/58 — apps/desktop/scripts/stage-native-deps.test.mjs
Objetivo: reformatação + tolerância Windows.
Alteração: majoritariamente prettier; 1 assertion de modo 0755 envolvida em `if (platform !== 'win32')`.
Risco: médio — ruído de formatação escondendo uma mudança de assertion.
Finding relacionado: HERMES-022, HERMES-036.
Status: FINDING

23/58 — apps/desktop/scripts/test-desktop.mjs
Objetivo: parametrizar productName/executableName.
Alteração: leitura de `build.productName`/`build.executableName` + prettier.
Risco: baixo. Correção necessária e bem feita.
Status: OK

24/58 — apps/desktop/src/app/chat/right-rail/preview-browser-bar.tsx
Objetivo: indicador "acesso do agente".
Alteração: +8 linhas.
Risco: MÉDIO — é um `<div role="status">` com texto estático "Acesso do agente ativo", sem binding a estado algum, e escondido abaixo do breakpoint `lg`.
Finding relacionado: HERMES-018.
Status: FINDING

25/58 — apps/desktop/src/app/settings/constants.ts
Objetivo: atualizar descrição/URL do Xiaomi MiMo.
Alteração: 2 linhas.
Risco: nenhum.
Status: OK

26/58 — apps/desktop/src/app/settings/custom-endpoints-settings.tsx
Objetivo: painel OmniRoute + i18n do painel de endpoints.
Alteração: +266/-33.
Risco: médio — `handleConfigureOmniRoute` reescreve o config global do Hermes; `useEffect` com dependência de string de tradução re-dispara o probe ao trocar idioma.
Cobertura: nenhum teste de componente.
Finding relacionado: HERMES-021.
Status: FINDING

27/58 — apps/desktop/src/app/settings/omniroute-preset.test.ts
Objetivo: testar o preset.
Alteração: novo, 87 linhas, 4 testes.
Risco: ALTO como evidência — o teste "preserves existing configuration" só verifica uma chave que o preset **não toca** (`max_iterations`). Nenhum teste verifica que chaves realmente sobrescritas seriam preservadas, porque elas não são.
Finding relacionado: HERMES-021.
Status: FINDING

28/58 — apps/desktop/src/app/settings/omniroute-preset.ts
Objetivo: montar a config Studio (MoA, delegação, aprovações, memória, MCP).
Alteração: novo, 111 linhas.
Risco: ALTO — `approvals.mode: 'smart'` com política em linguagem natural; sobrescreve chaves do usuário; endpoint local sem autenticação nem verificação de identidade.
Finding relacionado: HERMES-011, HERMES-016, HERMES-021.
Status: FINDING

29/58 — apps/desktop/src/global.d.ts
Objetivo: tipos das novas APIs do preload.
Alteração: +22 linhas.
Risco: nenhum.
Status: OK

30/58 — apps/desktop/src/i18n/catalog.ts
Objetivo: registrar pt-BR.
Alteração: +2 linhas.
Risco: nenhum.
Status: OK

31/58 — apps/desktop/src/i18n/en.ts
Objetivo: strings novas (omniroute, customEndpoints, agentAccess).
Alteração: +62 linhas.
Risco: baixo. `agentAccess: 'Agent access on'` é estático.
Finding relacionado: HERMES-018.
Status: OBS

32/58 — apps/desktop/src/i18n/languages.test.ts
Objetivo: cobrir normalização de locale pt-BR.
Alteração: +5 assertions.
Risco: baixo. Testes corretos.
Status: OK

33/58 — apps/desktop/src/i18n/languages.ts
Objetivo: opção pt-BR + aliases.
Alteração: +14 linhas.
Risco: baixo — alias `português` só com acento.
Finding relacionado: HERMES-040.
Status: OBS

34/58 — apps/desktop/src/i18n/pt-br.ts
Objetivo: catálogo pt-BR.
Alteração: novo, 449 linhas, ≈380 chaves.
Risco: ALTO em produto — `en.ts` tem ≈2.452 chaves. Cobertura ≈15%. `defineLocale` faz merge com inglês, então ~84% da interface aparece em inglês para o público-alvo declarado.
Finding relacionado: HERMES-017.
Status: FINDING

35/58 — apps/desktop/src/i18n/types.ts
Objetivo: tipar as novas seções e o locale pt-br.
Alteração: +60 linhas.
Risco: nenhum.
Status: OK

36/58 — apps/desktop/src/i18n/zh.ts
Objetivo: paridade chinesa das strings novas.
Alteração: +60 linhas.
Risco: nenhum. Nota: zh recebeu as strings novas; pt-BR recebeu; ja/ar/zh-hant não (são parciais por design).
Status: OK

37/58 — apps/desktop/src/main.tsx
Objetivo: título do HUD.
Alteração: 1 linha.
Risco: nenhum.
Status: OK

38/58 — docs/hermes-omniroute-studio.md
Objetivo: documentar o Studio.
Alteração: novo, 58 linhas.
Risco: ALTO como fonte de confiança — afirma comportamentos de segurança que o código não implementa (backups timestamped; bloqueio determinístico de comandos destrutivos; impossibilidade de marcar verificado sem evidência; redação por nome de campo).
Finding relacionado: HERMES-005, HERMES-006, HERMES-019, HERMES-020.
Status: FINDING

39/58 — gateway/slash_commands.py
Objetivo: `/goal draft` pausa para revisão.
Alteração: +18/-7.
Risco: médio — `mgr.pause(...) or state`: se `pause` retornar None a mensagem ainda afirma "paused for review".
Finding relacionado: HERMES-025.
Status: FINDING

40/58 — hermes_cli/cli_commands_mixin.py
Objetivo: mesmo gate no CLI.
Alteração: +9/-3.
Risco: médio — aqui o pause dispara para **qualquer** contrato, não só `draft`. O comentário afirma que `/goal <texto>` mantém comportamento imediato; o código contradiz o comentário. Divergência CLI × gateway.
Finding relacionado: HERMES-025.
Status: FINDING

41/58 — hermes_cli/config_defaults.py
Objetivo: descrições/URLs do Xiaomi Token Plan.
Alteração: 8 linhas de texto.
Risco: nenhum. `password: True` mantido no campo de chave.
Status: OK

42/58 — integrations/omniroute-daily-health.py
Objetivo: health check diário via cron.
Alteração: novo, 59 linhas.
Risco: baixo-médio — URL `127.0.0.1:20128` duplicada (terceira cópia do literal); contagem de erros por regex conta múltiplas ocorrências por linha e casa a palavra dentro de conteúdo de usuário.
Cobertura: nenhum teste.
Finding relacionado: HERMES-035.
Status: FINDING

43/58 — integrations/omniroute-mcp-bridge.mjs
Objetivo: ponte stdio para o MCP do OmniRoute + CLI de compressão.
Alteração: novo, 63 linhas.
Risco: CRÍTICO — resolve a raiz do pacote a partir de `process.env.OMNIROUTE_PACKAGE_ROOT` sem validação e importa/executa `bin/aliasResolver.mjs`, o loader `tsx` e `open-sse/mcp-server/server.ts` daquele diretório. Sem verificação de integridade, versão ou assinatura.
Cobertura: nenhum teste.
Finding relacionado: HERMES-002.
Status: FINDING

44/58 — package-lock.json
Objetivo: refletir a versão `0.17.0-omniroute.1`.
Alteração: 1 linha.
Risco: nenhum. Nenhuma dependência adicionada ou alterada.
Status: OK

45/58 — plugins/dz23-guardrail/__init__.py
Objetivo: gates determinísticos de segurança, evidência de verificação e relatório de tarefa.
Alteração: novo, 460 linhas.
Risco: CRÍTICO — provei por execução: denylist não cobre Windows; caminho relativo ignora o gate de workspace; `cwd` amplo neutraliza o gate; `echo` satisfaz o gate de verificação; teste falho satisfaz o gate; falsos positivos bloqueiam documentação e SQL legítimos.
Cobertura: 6 testes que confirmam o denylist contra si mesmo.
Finding relacionado: HERMES-005, HERMES-006, HERMES-007, HERMES-008, HERMES-020, HERMES-024, HERMES-031.
Status: FINDING

46/58 — plugins/dz23-guardrail/plugin.yaml
Objetivo: manifesto do plugin.
Alteração: novo, 20 linhas.
Risco: CRÍTICO — **não declara `kind`**, então vira `standalone`; plugins bundled standalone só carregam se listados em `plugins.enabled`, e nada no repo ou no instalador faz isso. Também duplica `provides_hooks` e `hooks`.
Finding relacionado: HERMES-001, HERMES-039.
Status: FINDING

47/58 — skills/software-development/product-studio/SKILL.md
Objetivo: skill de construção de produto.
Alteração: novo, 81 linhas.
Risco: baixo. Texto de alta qualidade — mas é instrução para o modelo, não controle executável.
Status: OBS

48/58 — .../product-studio/agents/openai.yaml
Objetivo: metadados de interface.
Alteração: novo, 4 linhas.
Risco: nenhum.
Status: OK

49/58 — .../references/browser-security.md
Objetivo: política de navegador.
Alteração: novo, 27 linhas.
Risco: nenhum. Advisory.
Status: OBS

50/58 — .../references/delivery-gates.md
Objetivo: checklist de gates.
Alteração: novo, 35 linhas.
Risco: nenhum. Advisory — nenhum gate é executável.
Status: OBS

51/58 — .../references/knowledge-and-rules.md
Objetivo: Knowledge Cards e AGENTS.md.
Alteração: novo, 32 linhas.
Risco: nenhum.
Status: OBS

52/58 — .../references/multi-agent-orchestration.md
Objetivo: roster e topologia de delegação.
Alteração: novo, 75 linhas.
Risco: nenhum. Consistente com `delegation.max_spawn_depth: 2`.
Status: OBS

53/58 — .../references/nontechnical-intake.md
Objetivo: intake de usuário leigo.
Alteração: novo, 34 linhas.
Risco: MÉDIO como política — "Install project dependencies automatically" combina com `approvals.mode: smart` e com a ausência total de detecção de `npm install`.
Finding relacionado: HERMES-011.
Status: FINDING

54/58 — .../references/spec-driven-delivery.md
Objetivo: ciclo de spec e Goal.
Alteração: novo, 29 linhas.
Risco: nenhum.
Status: OBS

55/58 — .../references/task-report.md
Objetivo: descrever o relatório de tarefa.
Alteração: novo, 16 linhas.
Risco: baixo — afirma "Native secret redaction is applied before the file is written", o que é verdade só quando o import funciona.
Finding relacionado: HERMES-020.
Status: OBS

56/58 — tests/gateway/test_goal_max_turns_config.py
Objetivo: testar a pausa do `/goal draft`.
Alteração: +45 linhas, 1 teste novo.
Risco: baixo. **É um dos poucos testes realmente bons do stage** — assere estado (`status == "paused"`, `paused_reason`) e não só texto. Falta o equivalente para o CLI.
Finding relacionado: HERMES-025.
Status: OBS

57/58 — tests/plugins/test_dz23_guardrail_plugin.py
Objetivo: testar o guardrail.
Alteração: novo, 142 linhas, 6 testes.
Risco: ALTO como evidência — carrega o plugin por `importlib.spec_from_file_location`, contornando todo o loader. Por isso o teste passa mesmo com o plugin desabilitado em produção. Testa o denylist apenas contra as 3 strings que ele já casa. Nenhum teste adversarial.
Finding relacionado: HERMES-001, HERMES-023.
Status: FINDING

58/58 — tests/skills/test_product_studio_skill.py
Objetivo: validar a skill.
Alteração: novo, 86 linhas, 6 testes.
Risco: ALTO como evidência — todas as assertions são `assert "<frase em inglês>" in body`. Nenhum comportamento é exercitado. Contribui para a contagem de "testes passando" sem provar nada.
Finding relacionado: HERMES-023.
Status: FINDING
```

**Contabilização:** 58/58 revisados. 22 com finding, 16 com observação, 20 OK.

---

## 5 — Critério de conclusão da auditoria

```text
58/58 staged files accounted for ............... SIM
107 MCP tools accounted for .................... PARCIAL — 106 enumerados estaticamente; ver HERMES-032
12 skipped tests investigated .................. PARCIAL — 11/12; ver HERMES-030
architecture mapped ............................ SIM — HERMES_OMNIROUTE_ARCHITECTURE.md
Electron security reviewed ..................... SIM — HERMES_OMNIROUTE_SECURITY.md
IPC reviewed ................................... SIM — 165 canais mapeados, 25 críticos detalhados
agents reviewed ................................ SIM (estático)
memory reviewed ................................ PARCIAL (estático; sem runtime)
Goal reviewed .................................. SIM
Product Studio reviewed ........................ SIM (estático)
Preview reviewed ............................... PARCIAL (estático)
SSH reviewed ................................... SIM
Caveman reviewed ............................... SIM
guardrails reviewed ............................ SIM — com prova de execução
cron reviewed .................................. PARCIAL (script lido; agendamento não testado)
pt-BR reviewed ................................. SIM — cobertura medida
installed application exercised ................ NÃO — BLOCKED_BY_EXTERNAL_DEPENDENCY
UI/UX reviewed ................................. PARCIAL (código; sem runtime)
performance investigated ....................... NÃO — NOT_MEASURED
failure paths investigated ..................... SIM (estático + execução do plugin)
test gaps documented ........................... SIM
P0-P3 findings classified ...................... SIM
improvement plan generated ..................... SIM
Codex handoff generated ........................ SIM
Git state preserved ............................ SIM
no commit ...................................... CONFIRMADO
no push ........................................ CONFIRMADO
```

**Razão das condições não atendidas:** o ambiente de auditoria é uma VM Linux com acesso somente-arquivo à máquina do usuário. Executar o aplicativo Windows, a suíte Electron, o build, o NSIS e o servidor MCP vivo exigiria execução no host Windows, que este ambiente não possui.

---

## 6 — Frase final

```text
AUDIT_COMPLETE=YES
STAGED_FILES_REVIEWED=58/58
MCP_TOOLS_ACCOUNTED=106/107
SKIPPED_TESTS_REVIEWED=11/12
P0=4
P1=12
P2=19
P3=6
CODEX_HANDOFF_CREATED=YES
CODEX_HANDOFF_PATH=audit/CODEX_HERMES_OMNIROUTE_FIX_PROMPT.md
GIT_COMMIT_CREATED=NO
GIT_PUSH_PERFORMED=NO
VERDICT=REQUIRES_CORRECTIONS
```
