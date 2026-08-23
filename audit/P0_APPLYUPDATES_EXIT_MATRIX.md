# P0 — Matriz de TODAS as saídas de `applyUpdates()` (§2C)

Auditoria de todos os retornos da função (`apps/desktop/electron/main.ts`), pós-correções
desta passada. Colunas: mata backend antes? backend restaurado? backoff gravado? marker
limpo? `updateInFlight` limpo? pode repetir no próximo boot? risco de boot-loop? risco de
instalação parcial?

`updateInFlight` é limpo em **TODAS** as saídas do corpo `try` pelo `finally` (`main.ts:4021-4023`).
As saídas 1-4 e 10 retornam ANTES de `updateInFlight = true`, então nunca o setam.

| # | Saída (`error`/tipo) | Momento vs kill | Backend restaurado | Backoff gravado | Marker | Repete no boot? | Boot-loop | Instalação parcial |
|---|---|---|---|---|---|---|---|---|
| 1 | `update-policy-manual-required` (fork/divergente) | ANTES (não mata) | não foi morto | não (não é falha) | nenhum | não (política estável) | **não** | não |
| 2 | `update-up-to-date` | ANTES | — | não | nenhum | não | **não** | não |
| 3 | `update-backoff-active` | ANTES | — | não (já em backoff) | nenhum | não (backoff vale) | **não** | não |
| 4 | `update-state-unknown` **[NOVO]** | ANTES | inicia backend | não | nenhum | reavalia; se seguir unknown, pula de novo | **não** | não |
| 5 | `update-gate-error` **[NOVO — fail-safe]** | ANTES | inicia backend | não | nenhum | reavalia | **não** | não |
| 6 | `update-already-running` (conflito de handoff) | ANTES do kill | não foi morto | não | dono é outro updater | sim, mas backend vivo | **não** | não (recusa) |
| 7 | lock não liberado (holder externo) | DEPOIS do kill | **sim** (`startHermes`) | **sim [NOVO]** | nenhum | backoff suprime | mitigado | não (aborta antes do spawn) |
| 8 | `venv-blocked` | DEPOIS do kill | sim | sim | nenhum | backoff suprime | mitigado | não (aborta antes do spawn) |
| 9 | `venv-probe-failed` | DEPOIS do kill | sim | sim | nenhum | backoff suprime | mitigado | não |
| 10 | `updater-spawn-failed` | DEPOIS do kill | sim | **sim [NOVO]** | pre-marker nomeia pid morto → auto-heal | backoff suprime | mitigado | não (spawn falhou, quit abortado) |
| 11 | `ok:true, manual` (CLI sem updater) | ANTES | não foi morto | não | nenhum | não | **não** | não |
| 12 | `ok:true, handedOff` (sucesso) | DEPOIS do kill → quit | app sai; updater relança | limpa no sucesso (`recordUpdateSuccess`) | updater é dono | n/a | **não** | n/a |

## Conclusões
- **Toda saída de FALHA posterior ao kill do backend agora grava backoff** (#7, #8, #9,
  #10). Antes, #7 e #10 não gravavam → re-tentavam no próximo boot → matavam o backend de
  novo (o sintoma do loop). Corrigido nesta passada.
- **Nenhuma saída deixa um caminho de boot-loop aberto.** As saídas destrutivas ou
  reiniciam o backend + registram backoff (7-10) ou nem chegam a matar o backend (1-6, 11).
- **`updateInFlight` limpo em todas** (finally). **Nenhuma instalação parcial**: todos os
  aborts pós-kill ocorrem ANTES do spawn do updater, exceto o sucesso (#12).
- **Residual não corrigido (P2):** #6/#12 têm janela **TOCTOU cross-process** — o marker é
  escrito só depois do kill (`~3941/3975`), então duas instâncias poderiam ambas passar o
  check e matar backends. Correção proposta: lock exclusivo (`wx`/O_EXCL) ANTES do primeiro
  passo destrutivo. Precisa de teste de concorrência → executor (não validável só em unit
  no container). Registrado em `FASE2_EXECUTOR_PROMPTS.md` (Executor 3).

## Evidência de teste (container Linux limpo)
- `update-policy` 13→ inclui J/K + canary; `update-backoff` inclui corrupt-file + canary;
  `update-decision` inclui a **matriz de falhas git** (git ausente, branch vazio, status
  falha, origin ausente, ref/branch ausente, ahead não-numérico, detached HEAD,
  behind-falha-segura) + canary.
- **Suíte electron completa: 1649 passed / 9 skipped** (era 1630 no baseline; +19 testes
  novos). `tsc -p tsconfig.electron.json` limpo.
- **Canaries verificados (mordem):** remover o guard de branch-desconhecido → 3 falham;
  neutralizar o backoff conservador de arquivo corrompido → 3 falham; fazer o collector
  devolver ok:true em falha de leitura → 2 falham. Restaurados → tudo verde.

`P0_UPDATER_STARTUP = SOURCE_ONLY_NOT_RUNTIME_VALIDATED` (source correto + endurecido +
matriz testada; **runtime Windows pendente de rebuild** — Executor 1).
