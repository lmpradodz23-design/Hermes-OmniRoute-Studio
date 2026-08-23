import { describe, expect, it } from 'vitest'

import {
  computeBackoffMs,
  DEFAULT_BASE_BACKOFF_MS,
  DEFAULT_MAX_BACKOFF_MS,
  INITIAL_BACKOFF_STATE,
  parseBackoffState,
  recordUpdateFailure,
  recordUpdateSuccess,
  shouldAttemptUpdate
} from './update-backoff'

describe('parseBackoffState — corrupt file must not re-open the loop (audit P2)', () => {
  it('an ABSENT/empty file is legitimate → INITIAL (no backoff)', () => {
    expect(parseBackoffState(null, 1_000).backoffUntil).toBe(0)
    expect(parseBackoffState('', 1_000).backoffUntil).toBe(0)
  })

  it('a PRESENT but corrupt file (invalid JSON) with now>0 applies a conservative backoff', () => {
    const now = 1_000_000
    const st = parseBackoffState('{not valid json', now)
    expect(st.backoffUntil).toBeGreaterThan(now)
    expect(st.retryCount).toBe(1)
    expect(shouldAttemptUpdate(st, now).attempt).toBe(false)
  })

  it('a non-object payload with now>0 also backs off (not INITIAL)', () => {
    const now = 1_000_000
    expect(parseBackoffState('42', now).backoffUntil).toBeGreaterThan(now)
  })

  it('backward-compatible: corrupt without now stays INITIAL (pure/tests)', () => {
    expect(parseBackoffState('{bad').backoffUntil).toBe(0)
  })

  it('CANARY: corrupt + now must never leave backoff at zero', () => {
    expect(parseBackoffState('{bad', 5_000).backoffUntil).not.toBe(0)
  })

  it('a VALID persisted state round-trips (backoffUntil respected)', () => {
    const raw = JSON.stringify({ lastResult: 'failed', lastAttemptAt: 10, backoffUntil: 9_999, retryCount: 2, lastFailureReason: 'x' })
    const st = parseBackoffState(raw, 5_000)
    expect(st.backoffUntil).toBe(9_999)
    expect(st.retryCount).toBe(2)
  })

  it('clamps an ABSURD FUTURE backoffUntil to now+max (corrupt file cannot disable updates forever)', () => {
    const now = 1_000_000
    const raw = JSON.stringify({ lastResult: 'failed', backoffUntil: now + 999 * 24 * 60 * 60 * 1000, retryCount: 1 })
    expect(parseBackoffState(raw, now).backoffUntil).toBe(now + DEFAULT_MAX_BACKOFF_MS)
  })

  it('does NOT clamp a within-window future backoffUntil', () => {
    const now = 1_000_000
    const within = now + 60 * 60 * 1000
    expect(parseBackoffState(JSON.stringify({ lastResult: 'failed', backoffUntil: within, retryCount: 1 }), now).backoffUntil).toBe(within)
  })

  it('CANARY: an absurd future backoffUntil must never exceed now+max', () => {
    const now = 5_000
    expect(parseBackoffState(JSON.stringify({ backoffUntil: now + 1e15 }), now).backoffUntil).toBeLessThanOrEqual(now + DEFAULT_MAX_BACKOFF_MS)
  })
})

describe('update backoff — breaks the update→fail→retry→kill-backend loop (P0)', () => {
  it('a fresh state attempts the update', () => {
    expect(shouldAttemptUpdate(INITIAL_BACKOFF_STATE, 1000).attempt).toBe(true)
  })

  it('D. after a failure, the next boot skips the update (backoff persisted)', () => {
    const now = 1_000_000
    const failed = recordUpdateFailure(INITIAL_BACKOFF_STATE, now, 'venv-probe-failed', 'failed')
    expect(failed.retryCount).toBe(1)
    expect(failed.backoffUntil).toBeGreaterThan(now)

    // a boot a minute later must NOT retry — it should go straight to backend start
    const soon = now + 60_000
    const decision = shouldAttemptUpdate(failed, soon)
    expect(decision.attempt).toBe(false)
    expect(decision.waitMs).toBeGreaterThan(0)
  })

  it('after the backoff window elapses, it attempts again', () => {
    const now = 1_000_000
    const failed = recordUpdateFailure(INITIAL_BACKOFF_STATE, now, 'blocked', 'blocked')
    const later = failed.backoffUntil + 1
    expect(shouldAttemptUpdate(failed, later).attempt).toBe(true)
  })

  it('backoff grows exponentially and is capped', () => {
    expect(computeBackoffMs(1)).toBe(DEFAULT_BASE_BACKOFF_MS)
    expect(computeBackoffMs(2)).toBe(DEFAULT_BASE_BACKOFF_MS * 2)
    expect(computeBackoffMs(3)).toBe(DEFAULT_BASE_BACKOFF_MS * 4)
    expect(computeBackoffMs(999)).toBe(DEFAULT_MAX_BACKOFF_MS) // capped
  })

  it('repeated failures escalate the retry count', () => {
    const now = 0
    let s = recordUpdateFailure(INITIAL_BACKOFF_STATE, now, 'x')
    s = recordUpdateFailure(s, now, 'x')
    s = recordUpdateFailure(s, now, 'x')
    expect(s.retryCount).toBe(3)
    expect(s.backoffUntil).toBe(now + computeBackoffMs(3))
  })

  it('a success resets the backoff', () => {
    const failed = recordUpdateFailure(INITIAL_BACKOFF_STATE, 1000, 'x')
    const ok = recordUpdateSuccess(2000)
    expect(ok.retryCount).toBe(0)
    expect(ok.backoffUntil).toBe(0)
    expect(shouldAttemptUpdate(ok, 3000).attempt).toBe(true)
  })
})
