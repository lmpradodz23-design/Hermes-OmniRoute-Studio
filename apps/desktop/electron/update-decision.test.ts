import { describe, expect, it } from 'vitest'

import {
  INITIAL_BACKOFF_STATE,
  parseBackoffState,
  recordUpdateFailure,
  recordUpdateSuccess,
  serializeBackoffState
} from './update-backoff'
import { decideUpdateGate, GateAction } from './update-decision'
import type { InstallState } from './update-policy'

const FORK: InstallState = {
  currentBranch: 'feature/hermes-omniroute-studio',
  updateBranch: 'main',
  behind: 370,
  ahead: 0,
  dirty: false,
  remoteIsOfficialUpstream: true
}

const OFFICIAL: InstallState = {
  currentBranch: 'main',
  updateBranch: 'main',
  behind: 5,
  ahead: 0,
  dirty: false,
  remoteIsOfficialUpstream: true
}

describe('decideUpdateGate — the wired orchestration path (P0)', () => {
  it('§4. a custom fork 370 behind main is SKIP_POLICY — the updater is never started', () => {
    const g = decideUpdateGate({ installState: FORK, backoffState: INITIAL_BACKOFF_STATE, now: 1000, force: false })
    expect(g.action).toBe(GateAction.SKIP_POLICY)
    expect(g.proceed).toBe(false)
  })

  it('an official clean checkout behind main PROCEEDS', () => {
    const g = decideUpdateGate({ installState: OFFICIAL, backoffState: INITIAL_BACKOFF_STATE, now: 1000, force: false })
    expect(g.action).toBe(GateAction.PROCEED)
    expect(g.proceed).toBe(true)
  })

  it('§3. THE BOOT-LOOP SCENARIO end to end: boot1 fails → persisted → boot2 skips', () => {
    const bootTime1 = 1_000_000

    // boot 1: official checkout, update attempted, venv probe fails → record + persist
    const gate1 = decideUpdateGate({
      installState: OFFICIAL,
      backoffState: INITIAL_BACKOFF_STATE,
      now: bootTime1,
      force: false
    })
    expect(gate1.proceed).toBe(true) // it would attempt

    const afterFailure = recordUpdateFailure(INITIAL_BACKOFF_STATE, bootTime1, 'venv-probe-timeout', 'failed')
    const persisted = serializeBackoffState(afterFailure) // written to disk

    // Hermes closes and reopens. boot 2 loads the persisted backoff.
    const reloaded = parseBackoffState(persisted)
    const bootTime2 = bootTime1 + 60_000 // a minute later
    const gate2 = decideUpdateGate({
      installState: OFFICIAL, // still "behind" — update still "available"
      backoffState: reloaded,
      now: bootTime2,
      force: false
    })

    // The fix: the updater does NOT start again — it backs off. Backend boots.
    expect(gate2.action).toBe(GateAction.SKIP_BACKOFF)
    expect(gate2.proceed).toBe(false)
    expect(gate2.waitMs).toBeGreaterThan(0)
  })

  it('after the backoff elapses, an official checkout attempts again', () => {
    const failed = recordUpdateFailure(INITIAL_BACKOFF_STATE, 0, 'x', 'failed')
    const g = decideUpdateGate({ installState: OFFICIAL, backoffState: failed, now: failed.backoffUntil + 1, force: false })
    expect(g.action).toBe(GateAction.PROCEED)
  })

  it('a real success clears the backoff so updates resume', () => {
    const ok = recordUpdateSuccess(5000)
    const g = decideUpdateGate({ installState: OFFICIAL, backoffState: ok, now: 6000, force: false })
    expect(g.action).toBe(GateAction.PROCEED)
  })
})

describe('§5 force audit — force is the ONLY bypass, and automatic never sets it', () => {
  it('AUTO (force=false) on a custom fork can NEVER proceed, even with no backoff', () => {
    const g = decideUpdateGate({ installState: FORK, backoffState: INITIAL_BACKOFF_STATE, now: 1, force: false })
    expect(g.proceed).toBe(false)
  })

  it('only an explicit force bypasses the fork guard', () => {
    const g = decideUpdateGate({ installState: FORK, backoffState: INITIAL_BACKOFF_STATE, now: 1, force: true })
    expect(g.action).toBe(GateAction.PROCEED)
    expect(g.reasons).toContain('force')
  })

  it('force also bypasses an active backoff (deliberate operator retry)', () => {
    const failed = recordUpdateFailure(INITIAL_BACKOFF_STATE, 0, 'x', 'failed')
    const g = decideUpdateGate({ installState: OFFICIAL, backoffState: failed, now: 1, force: true })
    expect(g.proceed).toBe(true)
  })
})

describe('backoff persistence is tolerant (never crashes boot)', () => {
  it('round-trips a real state', () => {
    const s = recordUpdateFailure(INITIAL_BACKOFF_STATE, 123, 'reason', 'blocked')
    expect(parseBackoffState(serializeBackoffState(s))).toEqual(s)
  })

  it('a missing / empty / corrupt file yields the initial state (no backoff)', () => {
    expect(parseBackoffState(null)).toEqual(INITIAL_BACKOFF_STATE)
    expect(parseBackoffState('')).toEqual(INITIAL_BACKOFF_STATE)
    expect(parseBackoffState('{not json')).toEqual(INITIAL_BACKOFF_STATE)
    expect(parseBackoffState('42')).toEqual(INITIAL_BACKOFF_STATE)
  })

  it('drops garbage fields but keeps a valid backoffUntil', () => {
    const parsed = parseBackoffState(JSON.stringify({ backoffUntil: 999, retryCount: 'x', lastResult: 'bogus' }))
    expect(parsed.backoffUntil).toBe(999)
    expect(parsed.retryCount).toBe(0)
    expect(parsed.lastResult).toBeNull()
  })
})
