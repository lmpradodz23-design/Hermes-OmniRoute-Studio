# AUTONOMOUS_MISSION_STATE

Checkpoint da skill `autonomous-mission-loop`. Complementa
`audit/AUTONOMOUS_EXECUTION_STATE.md` (que registra a missão de produto);
este arquivo registra a integração da skill ao catálogo nativo e os gates
de aceite dela.

| campo | valor |
|---|---|
| `mission_id` | `hermes-omniroute/skill-autonomous-mission-loop` |
| estado | `FIXING → RETESTING` concluídos; aguardando segunda passada dos auditores (R6) |
| `heartbeat_at` | 2026-08-22T23:05Z |
| `last_progress_at` | 2026-08-22T23:05Z |
| HEAD | `8a5e3d4` + correções da auditoria, ainda não commitadas |
| iteração | 4 |

## Iteração 4 — o fix loop da auditoria independente

As três auditorias (A/B/C) rodaram em paralelo e produziram
`audit/FINAL_THREE_AGENT_REVIEW.md`. Resultado do ciclo
`CANDIDATE_COMPLETED → FIXING → RETESTING`:

```
CRITICAL: 1 encontrado, 1 corrigido
HIGH:    13 encontrados, 13 corrigidos
MEDIUM:  13 encontrados, 8 corrigidos, 5 abertos e registrados
LOW:     11 encontrados, 7 corrigidos, 4 abertos e registrados
BLOCKERS_INTERNAL = 0
BLOCKERS_EXTERNAL = 2 (canal de segurança, remote do fork)
```

O achado mais importante foi contra o código desta própria missão: a detecção
de estagnação era **inerte** em produção — o fingerprint era medido depois dos
gates, então os artefatos que o gate escrevia contavam como progresso do agente.
O teste que a cobria passava porque `workspace_fingerprint` estava patcheado
para uma constante: **o mock removia exatamente a variável que quebrava.**

Corrigir isso exigiu três camadas, cada uma revelada pela anterior, e no
caminho apareceu um bug upstream independente: `git status --porcelain` devolve
` M src.py` na primeira edição e na décima, então o pulo de gate não re-rodava
a suíte depois de o agente editar um arquivo já modificado — a correção nunca
era testada.

Lição registrada para as próximas missões: **um mock que estabiliza a variável
sob teste não prova a feature, esconde o bug.** Os testes novos usam um
repositório git de verdade.

### Suítes depois das correções

| suíte | resultado |
|---|---|
| desktop `vitest ui` | 564 arquivos, **5386 passed**, 0 failed |
| desktop `vitest electron` | 118 arquivos, 1598 passed, 9 skipped |
| desktop `tsc --noEmit` | limpo |
| web `vitest` | 39 arquivos, 365 passed |
| `tests/skills` | 1797 passed |
| `tests/tools` (approval, osv, package-fetch) | 258 passed, incl. 38 regressões novas da auditoria |
| `tests/hermes_cli` (goals) | 90 passed |

## Objetivo

Integrar `autonomous-mission-loop` ao catálogo real de skills do Hermes —
descoberta, schema, carregamento, ativação, proveniência, documentação e
testes — **sem criar arquitetura paralela**, e implementar o que faltava de
fato no mecanismo existente para que checkpoint, retomada e detecção de
estagnação fossem verificáveis e não apenas descritos em texto.

## Gates de aceite

| gate | resultado | evidência |
|---|---|---|
| `CATALOG_DISCOVERY` | **PASS** | `_find_all_skills()` acha a skill num `HERMES_HOME` semeado; 1 ocorrência, sem duplicata — `tests/skills/test_autonomous_mission_loop_skill.py` |
| `SKILL_SCHEMA` | **PASS** | frontmatter parseia, nome bate com o diretório, descrição ≤60, linter do repositório limpo |
| `SKILL_LOAD` | **PASS** | `skill_view()` devolve 8.8 KB com os 9 conceitos obrigatórios |
| `SKILL_ACTIVATION` | **PASS** | ciclo real via `skills.disabled` do `config.yaml`: desativar some da listagem **e** bloqueia carregamento direto; reativar restaura; desativar vizinha não afeta esta |
| `CHECKPOINT` | **PASS** | estado sobrevive à troca de `GoalManager` (morte do executor simulada), incluindo contadores de estagnação e turnos gastos |
| `RESUME` | **PASS** | executor novo continua a contagem em vez de recomeçar; `resume()` abre janela nova sem amnésia |
| `STALL_DETECTION` | **PASS** | `classify_progress()` + loop real: 3 falhas equivalentes → `STRATEGY_CHANGE_REQUIRED` injetado no prompt; 5 turnos parados → `ESCALATE_TO_DIAGNOSTIC_AGENT` com pausa |
| `GUARDRAILS` | **PASS** | teste falha se o texto disser "ignore os guardrails"/"bypass"/"desabilite a segurança" ou se sumir a afirmação de que a skill não sobrepõe o piso hardline |
| `REGRESSION` | **PASS** | `tests/skills/` 1797 passed, 0 failed (era 54 failed antes desta iteração) |
| `FUNCTIONAL_SMOKE` | **PASS** | missão controlada sobre gate vermelho: gate falha → contagem → escalação → pausa → resume → retomada sem reinício (`tests/hermes_cli/test_goal_stall_detection.py`) |
| `BLOCKERS_INTERNAL` | **0** para esta integração |

Todos os testes foram verificados por canário: a correção foi desfeita e o
teste reprovou, depois refeita e o teste passou. Teste que não morde não é
evidência.

## O que foi implementado (não só documentado)

**Skill** — `skills/autonomous-ai-agents/autonomous-mission-loop/SKILL.md`,
registrada em `skills/PROVENANCE.json` como `firstParty`.

**Detecção de estagnação** — `hermes_cli/goals.py`. O loop de goals já pausava
por falha de infraestrutura (judge inalcançável, judge ilegível, orçamento de
turnos, gate sem retries). Não cobria o caso em que **nada quebra e nada anda**.
Agora cobre, com progresso medido e não declarado:

- progresso = workspace mudou **ou** falha mudou **ou** não houve falha;
- `heartbeat_at` e `last_progress_at` separados — heartbeat não é progresso;
- 3 falhas equivalentes → `STRATEGY_CHANGE_REQUIRED` (segue, com instrução
  explícita de trocar de estratégia e a proibição de verde artificial);
- 5 turnos sem progresso → `ESCALATE_TO_DIAGNOSTIC_AGENT` (pausa);
- campos novos com default, compatíveis com linhas antigas de `state_meta`.

**Documentação** — `docs/autonomous-mission-loop.md`.

## Achados corrigidos nesta iteração

**R5-01 — o gate de autoria do próprio repositório estava vermelho.**
O commit `900234c2` do fork (21/08) vendorizou 27 skills sem
`version`/`author`/`license`/`platforms` nem tags, com descrições de até 895
caracteres contra a hardline de 60. `tests/skills/test_authoring_standards.py`
reprovava 54 casos desde então. Corrigido nas 27: descrição curta que **recupera**
sinal (o índice de prompt já truncava em 60 e colava "..."), texto original do
upstream preservado literalmente em "When to Use", metadados derivados dos
manifestos de origem (`version` = commit vendorizado), e a adaptação registrada
em `SOURCES.json`/`SOURCE.json`. Resultado: 1797 passed, 0 failed.

**R5-02 — vazamento de segredo em `GET /api/env` (herdado do upstream).**
A linha de chave custom era montada com `_row(var_name, {})` — `is_password`
False lá dentro, logo `redacted_value` recebia o valor **cru** — e só depois o
dicionário era marcado `is_password = True`. A UI mascarava e oferecia
"revelar" um segredo que já tinha saído do servidor em texto puro, exatamente
para as chaves que aquele bloco existe para tratar como segredo por não
reconhecê-las. Corrigido passando a intenção para dentro de `_row`. Regressão
trancada por `tests/hermes_cli/test_env_custom_keys.py`, que agora afirma sobre
o payload inteiro — o vazamento não estava no campo que se olhava.
Atribuição: presente em `e30388e` (base upstream), portanto **não** introduzido
pelo fork. Candidato a reporte ao upstream — aguarda decisão do dono do projeto.

## Falhas conhecidas do ambiente (não do código)

| teste | causa |
|---|---|
| `test_browser_connect_dual_stack::test_skips_occupied_successor` | alocação de portas do contêiner difere do assumido pelo teste |
| `test_gateway_service::test_system_unit_includes_local_bin_in_path` | o teste instala unidade systemd; o contêiner roda como root e o código recusa por segurança |

Ambas reproduzem no HEAD sem nenhuma alteração minha. Registradas, não
mascaradas.

## Lacuna registrada — supervisor externo

A skill é política do agente; ela não ressuscita processo. O estado sobrevive
(`state_meta` + `/resume` + contadores persistidos), mas **a retomada depende de
alguém dispará-la**. Não existe supervisor externo que perceba a morte do
executor e suba outro. Registrado como tarefa técnica explícita da missão, não
como funcionalidade pronta.

## Workspace U1 — estado real (corrige o "PENDENTE" anterior)

A auditoria (Fase 1) provou que o U1 **já existe e é maduro** — não estava por
implementar. Ver `audit/WORKSPACE_U1_FINALIZATION_REPORT.md`.

```
WORKSPACE_U1_STATUS=EXISTE_MADURO + coerência/validação device pendentes
WORKSPACE_U1_IMPLEMENTED=shell, chat, composer, modelo/OmniRoute, tools, terminal,
  artifacts, files, diff, preview, sessões/resume, busca, palette, tema, pt-BR
  (tudo já presente); ESTA sessão: Agentes + Memória (starmap) no nav primário
  (commits c8be08d + seguinte, verificado: 198 testes sidebar + nav/parity 13 +
  tsc renderer limpo). Destinos reais, sem botão falso.
WORKSPACE_U1_PARTIAL=sidebar coerência, agent authoring, aba context unificada,
  goals authoring, memory inline, whatsapp/security como módulos próprios
WORKSPACE_U1_MISSING_VIEWS=Security Research (RAPTOR) surface, Product Studio
WORKSPACE_U1_E2E=BLOQUEADO_DEVICE (app buildado no Windows)
WORKSPACE_U1_INSTALLED_APP=BLOQUEADO_DEVICE (build+NSIS+instalação)
```

## Próxima ação

Trabalho device/backend restante do U1 entregue como prompts prontos em
`audit/WORKSPACE_U1_FINALIZATION_REPORT.md` (§"KNOWN LIMITATIONS") e
`audit/OPENWA_DEVICE_EXECUTOR_PROMPTS.md`. RAPTOR e OpenWA intactos; nenhuma
integração existente foi tocada pela mudança de U1 (só a sidebar + i18n).
