# Autonomous Mission Loop

Missões longas — as que atravessam várias sessões, terminam em release e
precisam sobreviver a interrupção — falham quase sempre do mesmo jeito: o
executor trabalha, relata progresso, e no fim está onde começou. Esta página
documenta as duas peças que o Hermes OmniRoute usa contra isso, e por que são
duas e não uma.

| peça | onde vive | o que faz |
|---|---|---|
| **skill** `autonomous-mission-loop` | `skills/autonomous-ai-agents/autonomous-mission-loop/SKILL.md` | política: como o agente conduz a missão |
| **loop de goals** | `hermes_cli/goals.py` | mecanismo: persistência, retomada, gates, orçamento, detecção de estagnação |

A skill é texto. O loop de goals é código. Texto não ressuscita processo — a
separação abaixo existe justamente para que ninguém confunda uma coisa com a
outra.

## O que a skill faz

Transforma uma tarefa grande em um ciclo que converge:

**AUDITAR → ENTENDER → PLANEJAR → EXECUTAR → TESTAR → INSPECIONAR → CORRIGIR →
RETESTAR → CHECKPOINT → CONTINUAR → AUDITORIA INDEPENDENTE → RELEASE**

O princípio único do qual todo o resto decorre: **a missão não termina porque o
executor acredita que terminou.** Termina quando evidência verificável satisfaz
gates objetivos.

## Quando usar

- a tarefa atravessa mais de uma sessão de contexto;
- precisa retomar depois de interrupção;
- tem critérios de conclusão objetivos e verificáveis;
- envolve auditar → corrigir → retestar em ciclo;
- termina em release, publicação ou entrega verificada.

## Quando **não** usar

Tarefa de um passo, pergunta factual, edição pontual, exploração sem critério
de conclusão. Se o custo do checkpoint supera o trabalho em si, a skill está
atrapalhando. Uma missão de 20 minutos não precisa de três auditores.

## Riscos

Autonomia longa erra em silêncio e caro. Os três modos que valem vigiar:

**Verde artificial.** É o risco central, e o mais tentador exatamente no
momento em que a missão está travada. Remover teste, enfraquecer assertion,
engolir exceção, hardcode apresentado como solução, mock apresentado como
integração — tudo isso "conclui" a missão e não entrega nada. A skill proíbe
explicitamente; a detecção de estagnação repete a proibição no prompt de
continuação, porque é quando ela precisa ser lida.

**Estagnação disfarçada de trabalho.** Turno após turno de atividade sem
progresso mensurável. Coberto por medição, não por promessa — ver abaixo.

**Custo.** Um loop persistente gasta orçamento enquanto ninguém olha. O
orçamento de turnos (`max_turns`), os retries por gate e a escalação por
estagnação são três tetos independentes; nenhum deles é opcional.

## Estado, checkpoint e retomada

A skill NÃO inventa um formato próprio de estado. Ela se apoia no subsistema de
goals que o Hermes já tem:

- o estado do goal é persistido em `state_meta`, chave `goal:<session_id>`;
- `/resume` recarrega o goal ativo;
- `GoalContract` carrega objetivo, verificação, restrições e `stop_when`;
- `GoalGate` carrega os comandos determinísticos que precisam passar.

Para o registro narrativo da missão (o que já foi feito, o que falta, blockers,
evidências), a skill mantém `audit/AUTONOMOUS_MISSION_STATE.md`. Os dois são
complementares: o `state_meta` é o que o runtime lê; o arquivo em `audit/` é o
que um humano — ou o próximo executor — lê para entender onde a missão está.

Ao iniciar, sempre: ler o checkpoint → `git status` → HEAD → diff → processos →
artefatos → comparar com o checkpoint. **Havendo missão incompleta, retomar.**
O projeto é a fonte de verdade; a conversa não é.

## Gates

Conclusão exige, por padrão:

```
BLOCKERS_INTERNAL = 0 · CRITICAL = 0 · HIGH = 0
lint · typecheck · unit · integration · security · build · functional_acceptance
· final_audit = PASS
```

`N/A` é aceitável — com justificativa registrada. Gate silenciosamente pulado
não é `N/A`, é gate reprovado.

## Detecção de estagnação

Implementada em `hermes_cli/goals.py` (`classify_progress`), não no texto da
skill — porque contar turnos é trabalho de código.

Progresso tem definição operacional: **o workspace mudou** (via
`workspace_fingerprint()`), **ou a falha mudou** (falha diferente é informação
nova: o diagnóstico andou), **ou não houve falha**. Nenhuma das três, e o turno
foi queimado.

```
3 falhas equivalentes  → STRATEGY_CHANGE_REQUIRED
                         (o loop segue, mas o prompt de continuação passa a
                          exigir estratégia diferente e hipótese descartada)
5 turnos sem progresso → ESCALATE_TO_DIAGNOSTIC_AGENT
                         (pausa: insistir daqui em diante queima orçamento)
```

`heartbeat_at` e `last_progress_at` são campos separados de propósito. O
heartbeat diz que o loop rodou; `last_progress_at` diz que ele andou. Um loop
que só bate heartbeat é precisamente o que precisa ser detectado.

`/goal resume` depois de uma escalação abre uma **janela nova** de tentativas —
zera os contadores mas preserva as assinaturas. Se a mesma falha voltar sobre o
mesmo workspace, a contagem recomeça e chega de novo ao limite. Janela nova,
não amnésia.

## Watchdog — a lacuna registrada

A skill é política de execução **do agente**. Ela não reinicia um processo
morto.

O loop de goals sobrevive à morte do executor no sentido de que o estado está
no `state_meta` e um novo `GoalManager` na mesma sessão retoma de onde parou
(coberto por `tests/hermes_cli/test_goal_stall_detection.py`). O que **não**
existe hoje é um supervisor externo que perceba a morte e suba o executor
sozinho: hoje isso depende de alguém chamar `/resume`.

Isso está registrado como tarefa técnica explícita da missão, não como
funcionalidade existente. Um supervisor de verdade monitoraria processo,
heartbeat, `last_progress_at`, checkpoint, PID e exit status; ao detectar
morte, preservaria o worktree (**nunca** reset destrutivo), subiria outro
executor e mandaria carregar o checkpoint.

Não finja que o checkpoint sozinho garante continuidade. Ele garante que a
retomada é possível — não que ela acontece.

## Limites de autonomia

A skill **não** suspende os guardrails do Hermes. Continuam valendo, sem
exceção: política de comandos, confinamento de filesystem, aprovações de alto
risco, limites de custo, destinos autorizados, proteção de segredos, e o piso
hardline de segurança.

Nunca executar automaticamente: apagar dados de produção, destruir banco,
sobrescrever backup, force push, reescrever histórico público, expor segredo,
gerar custo relevante, ou qualquer ação irreversível importante. A ação é
marcada como bloqueada e a missão segue com o resto.

`tests/skills/test_autonomous_mission_loop_skill.py` trava isso no texto da
skill: uma skill de autonomia é exatamente onde alguém escreveria "ignore os
guardrails", então o teste falha se essa frase aparecer — e falha também se a
afirmação contrária sumir.

## Dependência externa

```
BLOCKED_BY_EXTERNAL_DEPENDENCY
tarefa · motivo · evidência · o que é necessário · impacto
```

Credencial inexistente, autorização, hardware, serviço externo, pagamento,
decisão jurídica, operação destrutiva não autorizada. Um blocker externo **não**
encerra a missão: tudo que for independente continua.

## Três auditores independentes

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

Consolidação em `audit/FINAL_THREE_AGENT_REVIEW.md`, com cada achado
classificado `CRITICAL` `HIGH` `MEDIUM` `LOW` `IMPROVEMENT` `FALSE_POSITIVE`.
**Reproduza cada achado** antes de aceitar; descarte falso positivo com
evidência, não com opinião.

## Onde isto é testado

| gate | arquivo |
|---|---|
| descoberta, schema, carregamento, ativação, regressão do catálogo | `tests/skills/test_autonomous_mission_loop_skill.py` |
| estagnação, escalação, checkpoint, retomada | `tests/hermes_cli/test_goal_stall_detection.py` |
| proveniência e licença da skill | `tests/skills/test_skill_provenance.py` |
| gates de qualidade do goal | `tests/hermes_cli/test_goal_gates.py` |
