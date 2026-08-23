---
name: autonomous-mission-loop
description: Executa missoes longas ate gates objetivos passarem.
version: 1.0.0
author: DZ23, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [autonomous, mission, recovery, checkpoint, audit, release]
    related_skills: [product-studio, plan, test-driven-development, requesting-code-review]
---

# Autonomous Mission Loop

Transforma uma tarefa grande em um ciclo que converge:

**AUDITAR → ENTENDER → PLANEJAR → EXECUTAR → TESTAR → INSPECIONAR → CORRIGIR →
RETESTAR → CHECKPOINT → CONTINUAR → AUDITORIA INDEPENDENTE → RELEASE**

A missão não termina porque o agente acredita que terminou. Termina quando
evidência verificável satisfaz os gates.

## When to Use

Use quando a tarefa:

- levar mais de uma sessão de contexto;
- exigir retomada depois de interrupção;
- ter critérios de conclusão objetivos e verificáveis;
- envolver auditar → corrigir → retestar em ciclo;
- terminar em release, publicação ou entrega verificada.

**Não use** para: tarefa de um passo, pergunta factual, edição pontual,
exploração sem critério de conclusão, ou qualquer coisa em que o custo do
checkpoint supere o trabalho em si.

## O princípio

Nunca confunda:

| não é prova de | |
|---|---|
| atividade | progresso |
| teste passando | funcionalidade funcionando |
| código escrito | feature concluída |
| HTTP 200 | fluxo funcional |
| build bem-sucedido | produto operacional |
| ausência de erro visível | segurança |
| o executor dizer que terminou | conclusão |

## Estado persistente

Duas camadas, complementares — não invente uma terceira.

**O runtime** já persiste missão em `hermes_cli/goals.py`: estado do goal em
`state_meta` (`goal:<session_id>`), `/resume` recarrega, `GoalContract` carrega
objetivo e verificação, `GoalGate` carrega os comandos que precisam passar,
`classify_progress` mede estagnação. Use isso; não escreva um segundo mecanismo
ao lado.

**A missão** mantém `audit/AUTONOMOUS_MISSION_STATE.md` (ou `.agent/` quando
`audit/` não couber) — o registro que um humano ou o próximo executor lê — com,
no mínimo:

`mission_id` · objetivo · critérios de aceite · estado · iteração ·
`started_at` · `heartbeat_at` · `last_progress_at` · tarefa atual · concluídas ·
pendentes · blockers · `attempt_count` · falha atual · estratégia atual ·
arquivos modificados · testes e resultados · commits · artefatos · agentes
delegados · auditorias · próxima ação · instruções de retomada.

Atualizar depois de **cada progresso real**, não a cada tick.

## Retomada

Ao iniciar, sempre: ler o checkpoint → `git status` → HEAD → diff → processos →
artefatos → comparar com o checkpoint. Havendo missão incompleta, **retomar**.
Nunca recomeçar do zero. O projeto é a fonte de verdade; a conversa não é.

## Estados

`MISSION_CREATED` `AUDITING` `PLANNING` `EXECUTING` `TESTING` `INSPECTING`
`FIXING` `RETESTING` `CHECKPOINTING` `DELEGATING` `BLOCKED` `RELEASING`
`FINAL_AUDIT` `VALIDATING_RELEASE` `CANDIDATE_COMPLETED` `COMPLETED`
`FAILED_SAFE`

Exatamente um estado atual por missão.

## O loop

**A. Observar** o estado real, não só o checkpoint.
**B. Escolher** a menor ação que produza progresso verificável. Prioridade:
CRITICAL → segurança → perda de dados → blockers → quebrado → integração →
testes → UX → performance → melhorias.
**C. Executar.**
**D. Verificar** com os testes relevantes.
**E. Inspecionar** o resultado real — navegador, console, network, logs, banco,
API, filesystem, processos, containers.
**F. Decidir**: falhou → causa raiz → corrigir → retestar. Passou → registrar
evidência → avançar.
**G. Checkpoint.**
**H. Continuar** sem pedir autorização só para seguir.

## Anti-estagnação

Medir, nunca só repetir. Manter `heartbeat_at`, `last_progress_at`,
`attempt_count`, `same_failure_count`, `tests_passed_delta`, `files_changed`,
`completed_tasks_delta`. Heartbeat **não** é progresso.

```
tentativa 1 → falhou → diagnóstico
tentativa 2 → falhou igual → NOVA ESTRATÉGIA
tentativa 3 → sem progresso → STRATEGY_CHANGE_REQUIRED
persistiu   → ESCALATE_TO_DIAGNOSTIC_AGENT
```

No Hermes isto é código, não promessa: `classify_progress`
(`hermes_cli/goals.py`) mede progresso por mudança no workspace ou mudança na
falha, e o loop de goals aplica as diretivas abaixo.

3 tentativas equivalentes ⇒ `STRATEGY_CHANGE_REQUIRED`.
5 sem progresso ⇒ `ESCALATE_TO_DIAGNOSTIC_AGENT`, passando objetivo, evidências,
tentativas anteriores, logs, arquivos e hipóteses já descartadas.

## Skill ≠ watchdog

Esta skill é **política de execução do agente**. Ela não reinicia um processo
morto — texto não ressuscita PID.

Manter um processo vivo, detectar morte ou estagnação e disparar recuperação é
trabalho de um **supervisor externo** ao agente. Onde não existir supervisor,
registre a lacuna como tarefa técnica explícita da missão; não finja que o
checkpoint sozinho garante continuidade.

No Hermes hoje: o estado sobrevive (state_meta + `/resume`), mas a retomada
depende de alguém dispará-la. O checkpoint garante que retomar é possível —
não que acontece. A lacuna está registrada como tarefa técnica, não como
funcionalidade pronta.

Havendo supervisor, ele monitora processo, heartbeat, `last_progress_at`,
checkpoint, PID e exit status; ao detectar morte, preserva o worktree (**nunca**
reset destrutivo), sobe outro executor e manda carregar o checkpoint.

## Causa raiz

Proibido obter verde artificialmente: remover ou ignorar teste, enfraquecer
assertion, desabilitar verificação, engolir exceção, retornar sucesso falso,
hardcode apresentado como solução, mock apresentado como integração, remover
funcionalidade, reduzir segurança.

## Limites de autonomia

Esta skill **não** suspende os guardrails do Hermes. Continuam valendo:
política de comandos, confinamento de filesystem, aprovações de alto risco,
limites de custo, destinos autorizados, proteção de segredos, e o piso hardline
de segurança. Skill não sobrepõe hardline.

Não executar automaticamente: apagar dados de produção, destruir banco,
sobrescrever backup, force push, reescrever histórico público, expor segredo,
gerar custo relevante, ou qualquer ação irreversível importante. Marque como
bloqueada e siga com o resto.

## Dependência externa

Quando a tarefa depender de credencial inexistente, autorização, hardware,
serviço externo, pagamento, decisão jurídica ou operação destrutiva não
autorizada, registre:

```
BLOCKED_BY_EXTERNAL_DEPENDENCY
tarefa · motivo · evidência · o que é necessário · impacto
```

Um blocker externo **não** encerra a missão. Continue tudo que for independente.

## Conclusão

O executor não declara `COMPLETED`. Ao acreditar que terminou, declara
`CANDIDATE_COMPLETED` e inicia auditoria independente com três revisores que
**não veem as conclusões uns dos outros** antes de terminar:

- **A — Arquitetura/Engenharia**: código, integrações, concorrência,
  performance, manutenção, testes, recovery, packaging.
- **B — Segurança/DevSecOps**: ofensivo. Autenticação, autorização, segredos,
  filesystem, execução de comando, injeção, rede, gateway, plugins,
  dependências, CI/CD, instaladores, supply chain.
- **C — Produto/QA/UX**: usa o produto. Fluxos, interface, clareza,
  acessibilidade, responsividade, erros, estados vazios, loading, integrações,
  funcionalidade incompleta.

Consolidar em `audit/FINAL_THREE_AGENT_REVIEW.md`, classificando `CRITICAL`
`HIGH` `MEDIUM` `LOW` `IMPROVEMENT` `FALSE_POSITIVE`. **Reproduza cada achado**
antes de aceitar; descarte falso positivo com evidência.

Gates padrão para `COMPLETED`:

```
BLOCKERS_INTERNAL = 0 · CRITICAL = 0 · HIGH = 0
lint · typecheck · unit · integration · security · build · functional_acceptance
· final_audit = PASS
```

Registrar `N/A` com justificativa quando não se aplicar.

## Orçamento do loop

Limites configuráveis: máximo de tentativas equivalentes, agentes simultâneos,
orçamento de API, timeout por tarefa, timeout sem progresso. Ao atingir o
limite: trocar estratégia, reduzir escopo, ou registrar blocker. Nunca loop
infinito.

## Regra final

O objetivo não é trabalhar eternamente — é **convergir**.

Continue enquanto houver progresso executável. Recupere após interrupção. Mude
de estratégia na estagnação. Delegue quando outra especialidade for necessária.
Bloqueie com honestidade diante de dependência externa real. Nunca aceite a
autoavaliação do executor como prova. Só declare `MISSION_COMPLETED` com os
critérios objetivos comprovados.

Documentação completa: `docs/autonomous-mission-loop.md`.
