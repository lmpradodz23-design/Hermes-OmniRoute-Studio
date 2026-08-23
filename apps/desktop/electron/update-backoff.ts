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
 * Janela conservadora aplicada quando o arquivo de backoff EXISTE mas está
 * corrompido (JSON inválido / não-objeto). Um arquivo ausente/vazio é legítimo
 * (INITIAL, sem backoff); um arquivo PRESENTE porém ilegível pode ser um estado
 * de falha truncado — zerá-lo reabriria o loop de update. Sem `now` (default e
 * testes puros) mantém o comportamento antigo (INITIAL).
 */
function corruptBackoffState(now: number): BackoffState {
  if (!(now > 0)) {
    return { ...INITIAL_BACKOFF_STATE }
  }
  return recordUpdateFailure({ ...INITIAL_BACKOFF_STATE }, now, 'corrupt-backoff-file', 'failed')
}

/**
 * Parse tolerante do estado persistido (JSON em disco). Um arquivo ausente ou
 * vazio → INITIAL (sem backoff). Um arquivo PRESENTE porém corrompido/parcial
 * NUNCA derruba o boot; com `now` fornecido aplica uma janela de backoff
 * conservadora (não "esquece" o backoff de forma insegura). `backoffUntil` só é
 * respeitado se for um número finito. Puro/testável.
 */
export function parseBackoffState(raw: string | null | undefined, now = 0): BackoffState {
  if (!raw) {
    return { ...INITIAL_BACKOFF_STATE }
  }
  let obj: any
  try {
    obj = JSON.parse(raw)
  } catch {
    return corruptBackoffState(now)
  }
  if (!obj || typeof obj !== 'object') {
    return corruptBackoffState(now)
  }
  const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : 0)
  // Bound an absurd FUTURE backoffUntil (a corrupt/partial file claiming e.g. the
  // year 3000 must NOT disable updates indefinitely). When `now` is known, clamp
  // to now + max window. A negative/past value is harmless (shouldAttemptUpdate
  // just attempts), so only the upper bound needs clamping.
  const clampFuture = (v: number) =>
    now > 0 && v > now + DEFAULT_MAX_BACKOFF_MS ? now + DEFAULT_MAX_BACKOFF_MS : v
  const result = obj.lastResult
  return {
    lastResult: result === 'ok' || result === 'failed' || result === 'blocked' ? result : null,
    lastAttemptAt: num(obj.lastAttemptAt),
    backoffUntil: clampFuture(num(obj.backoffUntil)),
    retryCount: Math.max(0, Math.floor(num(obj.retryCount))),
    lastFailureReason: typeof obj.lastFailureReason === 'string' ? obj.lastFailureReason.slice(0, 500) : ''
  }
}

/** Serializa para persistência. */
export function serializeBackoffState(state: BackoffState): string {
  return JSON.stringify(state)
}
