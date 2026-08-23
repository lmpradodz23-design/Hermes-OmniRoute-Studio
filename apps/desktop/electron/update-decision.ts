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

/**
 * Coleta o InstallState a partir do git — PURO/injetável (sem Electron), para
 * que o matriz de falhas de leitura seja testável. Regra central (§5): UNKNOWN
 * != SAFE. Qualquer falha de leitura de uma dimensão que decide divergência
 * (branch / dirty / origin / ahead) → `{ ok: false }`, e o chamador PULA o
 * update (inicia o backend, não toca no runtime). `behind` é a única dimensão
 * "unknown = disponível": uma leitura falha nela vira `null`, não um erro.
 */
export interface InstallStateProbe {
  /** Executa um comando git; DEVE rejeitar/lançar em falha (git ausente, repo inválido, ref ausente, exit != 0). */
  git: (args: string[]) => Promise<string>
  /** Resolve a URL do origin; rejeita/lança quando origin está ausente/ilegível. */
  originUrl: () => Promise<string>
  /** Canonicaliza um remote e diz se é o upstream oficial. */
  isOfficialUpstream: (url: string) => boolean
  /** Branch que o desktop rastreia para update (ex.: 'main'). */
  updateBranch: string
}

export interface CollectResult {
  ok: boolean
  /** Preenchido apenas quando ok=true. */
  state: InstallState | null
  /** Preenchido apenas quando ok=false. */
  reason: string
}

export async function collectInstallState(probe: InstallStateProbe): Promise<CollectResult> {
  let currentBranch: string
  try {
    currentBranch = (await probe.git(['rev-parse', '--abbrev-ref', 'HEAD'])).trim()
  } catch (err) {
    return { ok: false, state: null, reason: `branch read failed: ${(err as Error).message}` }
  }
  if (!currentBranch) {
    return { ok: false, state: null, reason: 'current branch is empty (git could not determine HEAD)' }
  }

  let dirty: boolean
  try {
    dirty = (await probe.git(['status', '--porcelain'])).trim().length > 0
  } catch (err) {
    return { ok: false, state: null, reason: `status read failed: ${(err as Error).message}` }
  }

  let originUrl: string
  try {
    originUrl = (await probe.originUrl()) || ''
  } catch (err) {
    return { ok: false, state: null, reason: `origin read failed: ${(err as Error).message}` }
  }

  let ahead: number
  try {
    const aheadStr = (await probe.git(['rev-list', `origin/${probe.updateBranch}..HEAD`, '--count'])).trim()
    if (!/^\d+$/.test(aheadStr)) {
      // Ref ausente / saída não-numérica → não podemos afirmar "0 à frente".
      return { ok: false, state: null, reason: `ahead count unreadable ('${aheadStr}') — origin/${probe.updateBranch} missing?` }
    }
    ahead = Number(aheadStr)
  } catch (err) {
    return { ok: false, state: null, reason: `ahead read failed (origin/${probe.updateBranch} missing?): ${(err as Error).message}` }
  }

  // behind: unknown = disponível; falha vira null (seguro).
  let behind: number | null
  try {
    const behindStr = (await probe.git(['rev-list', `HEAD..origin/${probe.updateBranch}`, '--count'])).trim()
    behind = /^\d+$/.test(behindStr) ? Number(behindStr) : null
  } catch {
    behind = null
  }

  return {
    ok: true,
    reason: '',
    state: {
      currentBranch,
      updateBranch: probe.updateBranch,
      behind,
      ahead,
      dirty,
      remoteIsOfficialUpstream: probe.isOfficialUpstream(originUrl)
    }
  }
}

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
