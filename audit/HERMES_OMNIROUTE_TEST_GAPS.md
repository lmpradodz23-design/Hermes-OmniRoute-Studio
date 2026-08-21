# HERMES OMNIROUTE — TEST GAP MATRIX

O objetivo desta seção é responder: **o que os 1.549 testes não provam?**

## 1. Matriz feature × cobertura

Legenda: ✔ existe e é significativo · ~ existe mas fraco · ✗ ausente

| Feature | Unit | Integration | E2E | Failure | Security | Runtime | Gap principal |
|---|---|---|---|---|---|---|---|
| OmniRoute preset | ✔ | ✗ | ✗ | ✗ | ✗ | ✗ | Nenhum teste do fluxo "Configurar" real; teste de preservação verifica chave errada (HERMES-021) |
| 106 MCP tools | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | **Zero cobertura.** Nenhuma chamada, nenhum schema validado, nenhum teste de escopo |
| Bridge MCP | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | Arquivo executável sem um único teste (HERMES-002) |
| Escopos MCP | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | Nenhum teste de que um escopo ausente nega |
| Product Studio (skill) | ~ | ✗ | ✗ | ✗ | ✗ | ✗ | Só grep de frases em Markdown (HERMES-023) |
| Bundles gerenciados | ✔ | ✗ | ✗ | ✗ | ✗ | ✗ | Nenhum teste de EPERM/ENOSPC — o modo que derruba o boot (HERMES-009) |
| Memória | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | Nada no stage; duas superfícies concorrentes sem teste |
| Agentes / delegação | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | `max_spawn_depth`/`max_concurrent_children` do preset nunca exercitados |
| Goal | ✔ (gateway) | ~ | ✗ | ✗ | ✗ | ✗ | Sem teste do caminho CLI, que diverge (HERMES-025) |
| Preview | ✗ | ✗ | ~ | ✗ | ✗ | ✗ | Nenhum teste de porta ocupada, processo órfão, crash |
| SSH | ~ | ✗ | ✗ | ~ | ~ | ✗ | Caminho Windows real sem cobertura; teste live sempre pulado (HERMES-012) |
| Caveman | ✔ | ✗ | ✗ | ~ | ✗ | ✗ | Sem teste de stdout malformado, timeout, processo morto |
| Guardrails | ~ | ✗ | ✗ | ✗ | ✗ | ✗ | Testa o denylist contra si mesmo; **6 bypasses provados** (HERMES-005/006/007/008/024) |
| Carga do plugin | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | O teste contorna o loader com `importlib` — por isso HERMES-001 passou despercebido |
| Cron / health | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | Script sem nenhum teste |
| pt-BR | ✔ (locale) | ✗ | ✗ | ✗ | ✗ | ✗ | Testa normalização, **não** cobertura de tradução (HERMES-017) |
| Identidade/instalador | ✔ | ~ | ~ | ✗ | ✗ | ✗ | NSIS não testado além da geração |
| Update / upgrade | ~ | ✗ | ✗ | ✗ | ✗ | ✗ | Sem teste do fail-open de assinatura (HERMES-034) |
| Recovery | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | Nenhum teste de config corrompida, restart no meio de operação |
| IPC | ~ | ✗ | ~ | ✗ | ✗ | ✗ | 165 canais, nenhum teste de validação de argumento hostil |
| Aprovações | ✔ (core) | ~ | ✗ | ~ | ~ | ✗ | Nenhum teste de `mode: smart` no contexto do preset do Studio |

## 2. Anti-padrões de teste identificados no stage

### 2.1 Testes que verificam documentação, não comportamento
`tests/skills/test_product_studio_skill.py` — 6 funções, **100%** das assertions são `assert "<frase>" in <markdown>`. Falham quando alguém melhora a redação; passam quando o comportamento quebra.

### 2.2 Teste que confirma o denylist contra si mesmo
`test_destructive_commands_are_blocked_by_hook` usa exatamente as três strings que os três regexes casam. Zero casos adversariais. Um único caso a mais (`del /s /q`) teria exposto HERMES-005 no dia em que o código foi escrito.

### 2.3 Teste que contorna o mecanismo que deveria validar
`test_dz23_guardrail_plugin.py:7-8` carrega o plugin por `importlib.util.spec_from_file_location`. Isso pula descoberta, manifesto, `kind`, `plugins.enabled` e `register()` real. **É a razão pela qual HERMES-001 — o plugin nunca carrega — não foi detectado por 1.549 testes verdes.**

### 2.4 Assertions que viram no-op na plataforma de release
8 sites com `if (process.platform !== 'win32') { …assert… }`. Reportam PASS sem asserir. Três cobrem propriedades de segurança. (HERMES-022)

### 2.5 Testes adaptados ao invés de cobrir o caminho real
`ssh-connection.test.ts` — `mux: true` injetado em 9 construtores para manter os testes exercitando o caminho multiplexado, que não é o default no Windows. (HERMES-012)

### 2.6 Teste cujo nome afirma mais do que ele verifica
`"preserves existing configuration"` verifica uma chave que o código não toca. (HERMES-021)

### 2.7 Teste que parece provar redação de segredo e não exercita o redator
`test_task_report_tracks_evidence_without_logging_tool_payloads` assere `"do-not-log-this" not in report`. Isso é trivialmente verdadeiro: o relatório **nunca** inclui argumentos de ferramenta. O teste não passa por `_redact` e não cobre seu fail-open. (HERMES-020)

## 3. Testes que faltam — proposta priorizada

### P0 — provam ou refutam os achados críticos
1. **Carga real do plugin.** Subir `PluginManager` com o `config.yaml` que o instalador produz; asserir que `dz23-guardrail` está `enabled=True` e que `pre_tool_call` é invocado numa chamada de ferramenta.
2. **Denylist adversarial.** Tabela parametrizada: 12 comandos destrutivos (Windows + POSIX + SQL + Git + Docker) devem bloquear; casos negativos (`git clean -n`, doc mencionando `rm -rf`) não devem.
3. **Gate de verificação honesto.** exit≠0 sem "error" → não verifica; `echo npm test` → não verifica; `pytest` exit 0 → verifica; resultado sem exit_code → não verifica.
4. **Escopo de workspace.** `../`, `..\`, symlink/junction, UNC, `~`; cwd amplo → ainda exige aprovação.
5. **Bridge MCP com raiz hostil.** `OMNIROUTE_PACKAGE_ROOT` apontando para diretório temporário → recusa, não importa.
6. **Escopos MCP.** Escopo mínimo + `plugin_install` → `isError` com `missing_scopes`; conjunto default não contém `write:plugins`.
7. **IPC `file:`.** `openExternal('file:///C:/Windows/System32/calc.exe')` → recusado; `writeTextFile` fora das raízes → recusado.

### P1 — cobrem o que o produto anuncia
8. Cobertura de tradução por locale, com limiar que falha abaixo de 90% para locales anunciados.
9. Falha de I/O nos `installBundled*` → boot continua, estado reporta erro.
10. Backup timestamped existe após atualizar um arquivo gerenciado.
11. `_redact` indisponível → nenhum relatório escrito.
12. Preset preserva `goals.max_turns` e `approvals.mode` definidos pelo usuário.
13. `/goal draft` no CLI pausa igual ao gateway; `pause` falhando → mensagem não afirma pausa.
14. SSH parametrizado por `mux: [true,false]`; teste live contra container OpenSSH efêmero em CI.
15. ACL Windows de `connection.json` verificada lendo a ACL de volta.

### P2 — resiliência e integração
16. Injeção de falha: MCP indisponível, tool retorna erro, timeout, rede cai, preview morre, porta ocupada, config corrompida, restart no meio da operação. Para cada uma: o sistema reporta `FAILED`/`BLOCKED`, nunca sucesso aparente.
17. Prompt injection: conteúdo hostil vindo de `web_fetch`, de arquivo, de memória e de resposta MCP tentando induzir uso de ferramenta privilegiada. Asserir que a aprovação é exigida.
18. Smoke E2E do app instalado: startup, navegação, troca de idioma, configurar OmniRoute, abrir preview, shutdown limpo, zero processos órfãos, zero unhandled rejections no log.
19. Instalador: instalação limpa, upgrade sobre versão anterior, reinstalação, desinstalação, arquivos residuais, comportamento com o app aberto.

## 4. Regra de higiene proposta

Nenhum teste deve conter `process.platform` dentro do corpo. Use `test.skipIf`, que reporta skip. Nenhum skip deve ser anônimo: o runner deve imprimir a lista nomeada com o motivo.
