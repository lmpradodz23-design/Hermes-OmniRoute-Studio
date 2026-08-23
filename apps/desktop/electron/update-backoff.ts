'use strict'

/**
 * update-backoff.ts
 *
 * Impede o loop "update falha → tenta de novo no próximo boot → mata o backend
 * de novo". PURO/testável. Um update que falhou/foi bloqueado entra em backoff
 * exponencial persistido; enquanto o backoff vale, o boot NÃO tenta atualizar —
 * ele parte direto para START_BACKEND.
 */

export type UpdateResult = 'ok' | 'failed' | 'blocked'

export interface BackoffState {
  lastResult: UpdateResult | null
  lastAttemptAt: number
  backoffUntil: number
  retryCount: number
  lastFailureReason: string
}

export const INITIAL_BACKOFF_STATE: BackoffState = {
  lastResult: null,
  lastAttemptAt: 0,
  backoffUntil: 0,
  retryCount: 0,
  lastFailureReason: ''
}

export const DEFAULT_BASE_BACKOFF_MS = 15 * 60 * 1000 // 15min
export const DEFAULT_MAX_BACKOFF_MS = 24 * 60 * 60 * 1000 // 24h

export interface AttemptDecision {
  attempt: boolean
  /** Quando attempt=false, quanto falta do backoff (ms). */
  waitMs: number
  reason: string
}

/**
 * Decide se um auto-update pode ser tentado agora. Em backoff → não tenta
 * (deixa o boot seguir para o backend). Fora do backoff → tenta.
 */
export function shouldAttemptUpdate(state: BackoffState, now: number): AttemptDecision {
  if (state.backoffUntil > now) {
    return {
      attempt: false,
      waitMs: state.backoffUntil - now,
      reason: `em backoff após ${state.retryCount} falha(s): ${state.lastFailureReason || state.lastResult || 'desconhecido'}`
    }
  }
  return { attempt: true, waitMs: 0, reason: 'sem backoff ativo' }
}

/** Backoff exponencial com teto: base * 2^(retry-1), limitado a max. */
export function computeBackoffMs(
  retryCount: number,
  base = DEFAULT_BASE_BACKOFF_MS,
  max = DEFAULT_MAX_BACKOFF_MS
): number {
  const n = Math.max(1, Math.floor(retryCount))
  const raw = base * 2 ** (n - 1)
  return Math.min(max, raw)
}

/** Registra uma falha/bloqueio: incrementa retry e agenda o próximo attempt. */
export function recordUpdateFailure(
  state: BackoffState,
  now: number,
  reason: string,
  result: Exclude<UpdateResult, 'ok'> = 'failed',
  opts: { base?: number; max?: number } = {}
): BackoffState {
  const retryCount = Math.max(0, Math.floor(state.retryCount)) + 1
  const backoffMs = computeBackoffMs(retryCount, opts.base, opts.max)
  return {
    lastResult: result,
    lastAttemptAt: now,
    backoffUntil: now + backoffMs,
    retryCount,
    lastFailureReason: String(reason || '').slice(0, 500)
  }
}

/** Registra sucesso: zera o backoff. */
export function recordUpdateSuccess(now: number): BackoffState {
  return { lastResult: 'ok', lastAttemptAt: now, backoffUntil: 0, retryCount: 0, lastFailureReason: '' }
}

/**
 * Parse tolerante do estado persistido (JSON em disco). Um arquivo ausente,
 * vazio, corrompido ou parcial NUNCA derruba o boot nem "esquece" o backoff de
 * forma insegura — campos inválidos caem para o INITIAL (sem backoff), e um
 * `backoffUntil` só é respeitado se for um número finito. Puro/testável.
 */
export function parseBackoffState(raw: string | null | undefined): BackoffState {
  if (!raw) {
    return { ...INITIAL_BACKOFF_STATE }
  }
  let obj: any
  try {
    obj = JSON.parse(raw)
  } catch {
    return { ...INITIAL_BACKOFF_STATE }
  }
  if (!obj || typeof obj !== 'object') {
    return { ...INITIAL_BACKOFF_STATE }
  }
  const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : 0)
  const result = obj.lastResult
  return {
    lastResult: result === 'ok' || result === 'failed' || result === 'blocked' ? result : null,
    lastAttemptAt: num(obj.lastAttemptAt),
    backoffUntil: num(obj.backoffUntil),
    retryCount: Math.max(0, Math.floor(num(obj.retryCount))),
    lastFailureReason: typeof obj.lastFailureReason === 'string' ? obj.lastFailureReason.slice(0, 500) : ''
  }
}

/** Serializa para persistência. */
export function serializeBackoffState(state: BackoffState): string {
  return JSON.stringify(state)
}
