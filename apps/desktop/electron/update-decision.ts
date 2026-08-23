'use strict'

/**
 * update-decision.ts
 *
 * A ÚNICA decisão de gate do updater — combina o fork-guard (update-policy) com
 * o backoff persistido (update-backoff) num resultado puro/testável. main.ts
 * consome isto no chokepoint applyUpdates; os testes exercitam o caminho de
 * orquestração real (não só os helpers), incluindo o cenário exato do boot-loop:
 * update falha → backoff persistido → segundo boot NÃO tenta de novo.
 *
 * `force` = intenção explícita e privilegiada do operador (ex.: botão "Atualizar
 * mesmo assim"). NUNCA deve vir de startup automático, auto-check, retry ou
 * estado stale. O caminho automático sempre passa force=false.
 */

import { type BackoffState, shouldAttemptUpdate } from './update-backoff'
import { type InstallState, resolveUpdatePolicy, UpdatePolicy } from './update-policy'

export enum GateAction {
  PROCEED = 'proceed', // pode iniciar o update
  SKIP_POLICY = 'skip_policy', // fork/divergente → MANUAL_REQUIRED
  SKIP_UP_TO_DATE = 'skip_up_to_date', // nada a fazer
  SKIP_BACKOFF = 'skip_backoff' // em backoff após falha — NÃO re-tentar
}

export interface GateInputs {
  installState: InstallState
  backoffState: BackoffState
  now: number
  /** Override explícito do operador. Automático = sempre false. */
  force: boolean
}

export interface GateResult {
  action: GateAction
  policy: UpdatePolicy
  reasons: string[]
  /** Quando SKIP_BACKOFF, quanto falta (ms). */
  waitMs: number
  /** true só para PROCEED — atalho para o chamador. */
  proceed: boolean
}

/**
 * Decide se um update pode começar AGORA. Ordem: force → fork-policy → backoff.
 * Qualquer SKIP significa "não atualize; inicie o backend normalmente".
 */
export function decideUpdateGate(input: GateInputs): GateResult {
  // force = intenção explícita do operador: ignora policy e backoff.
  if (input.force) {
    return { action: GateAction.PROCEED, policy: UpdatePolicy.AUTO, reasons: ['force'], waitMs: 0, proceed: true }
  }

  const decision = resolveUpdatePolicy(input.installState)

  if (decision.policy === UpdatePolicy.MANUAL_REQUIRED) {
    return { action: GateAction.SKIP_POLICY, policy: decision.policy, reasons: decision.reasons, waitMs: 0, proceed: false }
  }

  if (decision.policy === UpdatePolicy.UP_TO_DATE) {
    return { action: GateAction.SKIP_UP_TO_DATE, policy: decision.policy, reasons: [], waitMs: 0, proceed: false }
  }

  // AUTO permitido pela política — mas respeita o backoff persistido de falhas.
  const attempt = shouldAttemptUpdate(input.backoffState, input.now)
  if (!attempt.attempt) {
    return {
      action: GateAction.SKIP_BACKOFF,
      policy: UpdatePolicy.AUTO,
      reasons: [attempt.reason],
      waitMs: attempt.waitMs,
      proceed: false
    }
  }

  return { action: GateAction.PROCEED, policy: UpdatePolicy.AUTO, reasons: [], waitMs: 0, proceed: true }
}
