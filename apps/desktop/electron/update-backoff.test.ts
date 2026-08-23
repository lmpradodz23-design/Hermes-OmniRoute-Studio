import { describe, expect, it } from 'vitest'

import {
  computeBackoffMs,
  DEFAULT_BASE_BACKOFF_MS,
  DEFAULT_MAX_BACKOFF_MS,
  INITIAL_BACKOFF_STATE,
  recordUpdateFailure,
  recordUpdateSuccess,
  shouldAttemptUpdate
} from './update-backoff'

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
