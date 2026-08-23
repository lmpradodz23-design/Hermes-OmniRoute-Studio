# P0 — Regressão de startup do Hermes instalado (diagnóstico)

Status: **CAUSA RAIZ IDENTIFICADA com evidência** (desktop.log real lido). Nenhum
dado apagado; nada executado via WSL contra binários Windows.

## Sintoma

App instalado (v0.20.4) falha o boot: `Hermes backend exited before it became
ready (1)`. Intermitente — o backend às vezes chega a READY (08:05:57), às vezes
não.

## Causa raiz (encadeada, provada pelo log)

1. **`.update_check` = `{"behind": 370, "ver": "0.20.4"}`** — o checkout
   `hermes-agent` está 370 commits atrás do branch que o desktop rastreia para
   auto-update. `DEFAULT_UPDATE_BRANCH = 'main'` (main.ts:853). **A instalação é
   um FORK** (`feature/hermes-omniroute-studio`); o auto-update mira `main`.
2. O auto-update dispara periodicamente (08:12:37). Ele **mata o backend em
   execução** para liberar o venv shim (`venv shim unlocked; safe to proceed` →
   `Hermes backend exited (1)` em 60ms) — o exit(1) é o backend sendo
   **terminado para o handoff**, não um crash de código.
3. O update não completa: os logs `logs/update.log` / `logs/hermes-update.log`
   mostram `Other Hermes processes are running from this install's venv: PID …
   python.exe … -m hermes_cli.main gateway run ← gateway`. No Windows o
   **gateway persistente segura os `.pyd`**, então o update de dependências
   falharia pela metade.
4. O **venv-blocker probe do desktop falha com `exit code -1`** (o subprocesso
   `venvPython -m hermes_cli._scan_venv_blockers` morre/timeout durante o
   handoff) → `Update aborted: could not verify the Hermes installation is free`.
5. O update aborta **mas `behind:370` não é limpo** → na próxima passada o update
   dispara **de novo**, mata o backend **antes de READY** → `exited before it
   became ready (1)` → **boot falha**. Loop (§8 exatamente).

## Achado de SEGURANÇA (crítico)

O auto-update mira **`main`** enquanto a instalação é o **fork do usuário**, 370
commits atrás. Se o update "tivesse sucesso", ele **sobrescreveria o trabalho do
fork com o upstream main**. Ou seja: o loop, ironicamente, vinha **protegendo o
fork** ao falhar. **NÃO forçar o update / NÃO usar `--force-venv`** — isso
destruiria o trabalho do fork.

## Recuperação imediata segura (usuário roda no Windows — não executo processo Windows)

Ordem, preservando dados (nada de apagar state.db/venv):

1. Fechar o Hermes por completo (inclusive o ícone da bandeja).
2. Parar o gateway persistente (o dono do venv):
   `hermes gateway stop` — ou Gerenciador de Tarefas → encerrar
   `python.exe … hermes_cli.main gateway run`.
3. **Desligar o auto-update OU fixar o branch no fork** para o update parar de
   mirar `main` (Configurações → Updates; ou o override em
   `%APPDATA%\HermesOmniRoute\updates.json`). NÃO aceitar "update to main".
4. Reabrir — sem o gateway segurando o venv e sem o update disparando contra
   main, o backend chega a READY (como em 08:05:57).

Backups emergenciais do state.db já existem (o próprio updater criou:
`state.db.pre-update-emergency-*.bak`). state.db header OK (`headerOk=true`).

## Correções de causa raiz (source; exigem rebuild — §8/§12/§13)

1. **Não auto-atualizar um fork/checkout divergente para `main`.** Se o branch
   local ≠ branch de update, ou há commits locais à frente / working tree sujo,
   NÃO disparar o update automático (evita clobber do fork). Rastrear o branch
   do próprio checkout, não `main` fixo.
2. **Backoff / não relançar o update a cada passada quando ele falha/está
   bloqueado.** Um update abortado (probe-failure ou blocked) deve: deixar o
   backend saudável rodando, mostrar a mensagem acionável UMA vez, e não
   re-disparar em loop nem matar o backend antes de READY.
3. **Probe robusto:** quando o gateway segura o venv, reportar `blocked` (com o
   PID, como o updater CLI já faz) em vez de `exit -1 / could not verify`.
4. **Teste de regressão:** update dispara com gateway segurando venv → estado de
   update limpo/rollback → backend inicia UMA vez → sem loop → READY. Também:
   probe spawn-failure/timeout; checkout de fork não dispara update para main.

## Correção implementada (source; commit `e719dea`) — Opção C

Fix da causa raiz, com testes + canaries (electron project: **1619 passed, 0
failed**; tsc electron limpo):

- `electron/update-policy.ts` — `resolveUpdatePolicy`: auto-update SÓ para
  checkout oficial/limpo/no branch de update; fork/divergente/sujo/commits-locais/
  remote-não-oficial → `MANUAL_REQUIRED` (nunca sobrescreve o fork). (tests A/F/G/H)
- `electron/update-backoff.ts` — update que falha entra em backoff exponencial
  persistido; o próximo boot NÃO re-tenta (vai direto ao backend). Quebra o loop.
  (test D)
- `electron/venv-blocker-scan.ts` — `classifyProbeError`: o `-1` real é
  **timeout** (venv preso pelo gateway); distingue spawn_failed/access_denied/
  nonzero_exit; nunca lê falha de probe como "livre". (test C)
- `electron/main.ts` — fork-guard no chokepoint `applyUpdates()`: a menos de
  `force`, para fork/divergente PULA o handoff destrutivo e inicia o backend.
  Falha SAFE.

Canaries: Q (remove fork-guard → test falha), R (remove backoff → test falha),
C (probe -1 tratado como livre → test falha). Todos mordem.

**Efeito requer rebuild+instalação** (o binário v0.20.4 não contém o fix) —
validação de runtime no executor (`U1_WINDOWS_FINAL_EXECUTOR.md`).

## Wiring do backoff comprovado (commit `23f561c`) — fecha a lacuna apontada

O `update-backoff.ts` deixou de ser helper órfão: está WIRED no caminho real.

- **Consulta ANTES de atualizar:** `applyUpdates()` (chokepoint) chama
  `decideUpdateGate()` no TOPO (antes de `updateInFlight`, de qualquer kill de
  backend ou marker). Se `!proceed` → inicia o backend e retorna.
- **Persistência:** `userData/update-backoff.json` (estado de ATUALIZAÇÃO,
  separado do state.db). `read/writeUpdateBackoffState` em main.ts;
  `parseBackoffState` tolerante (arquivo ausente/corrompido → sem backoff).
- **`recordUpdateFailure` nos pontos reais:** `venv-blocked` e
  `venv-probe-failure` (as falhas síncronas do loop observado) + no resultado do
  handoff destacado (falha). `recordUpdateSuccess` no handoff OK (limpa backoff).
- **Teste de orquestração (não só helper):** `update-decision.test.ts` prova o
  cenário exato — boot1 falha → persiste → **boot2 detecta backoff → updater NÃO
  inicia → backend boota** (§3); fork no chokepoint → SKIP_POLICY, updater não
  spawna (§4); force audit (§5). Canaries A (remove consulta ao backoff → falha)
  e C (auto força force=true → falha) mordem.
- **§9 ordem:** o gate roda ANTES de qualquer stop-backend/marker (placement no
  topo de applyUpdates).
- **§5 force:** nenhum caller automático passa force (renderer chama
  `applyUpdates()` sem args; update-all passa `{}`); só ação explícita do operador.

Classificação (§14):
```
FORK_POLICY_FIX=SOURCE_PASS (wired no chokepoint + teste integrado)
VENV_BLOCKER_CLASSIFICATION=SOURCE_PASS
UPDATE_BACKOFF_MODULE=PASS
UPDATE_BACKOFF_RUNTIME_WIRING=SOURCE_PASS (wired + persistido + teste de orquestração)
UPDATE_LOOP_FIX=SOURCE_PASS  (NÃO RUNTIME_PASS — exige rebuild)
OPEN_INTERNAL_FIXABLE(source)=0 ; RUNTIME pendente de rebuild+validação
```

Follow-up honesto (NÃO feito): **§8 auto-graceful-shutdown do gateway pelo
updater**. Hoje, gateway segurando o venv → o updater faz backoff seguro
(backend boota, sem force-kill, sem perda) em vez de loopar; mas completar um
update ainda pediria parar o gateway manualmente (irrelevante para fork, cujo
auto-update está desativado). Detectar o gateway próprio → shutdown gracioso →
timeout → verificar → atualizar fica como melhoria registrada.

## state.db — validação não destrutiva (§16)

`PRAGMA quick_check = ok`, `PRAGMA integrity_check = ok`, 23 tabelas, 598016
bytes. **O banco NÃO é a causa** — confirma o updater-loop. Nada apagado;
backups emergenciais preservados.

## Classificação

```
ROOT_CAUSE = auto-update (behind:370 vs main) mata o backend p/ handoff; update
  bloqueado pelo gateway que segura o venv; probe falha (-1); estado não limpo →
  loop → boot falha. Backend exit(1) = terminação para handoff, NÃO crash de código.
FORK_SAFETY = auto-update mira main sobre o fork → NÃO forçar update
STATE_DB_STATUS = íntegro (headerOk), backups emergenciais presentes, NÃO tocado
VENV_STATUS = presente; o gateway o mantém locado (causa do probe -1)
DATA_DELETED = nenhum
```
