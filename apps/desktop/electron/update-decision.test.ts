import { describe, expect, it } from 'vitest'

import {
  INITIAL_BACKOFF_STATE,
  parseBackoffState,
  recordUpdateFailure,
  recordUpdateSuccess,
  serializeBackoffState
} from './update-backoff'
import { collectInstallState, decideUpdateGate, GateAction, type InstallStateProbe } from './update-decision'
import { resolveUpdatePolicy, UpdatePolicy, type InstallState } from './update-policy'

// A fake git for the collector: map argv-joined command → value, or an Error to
// simulate a non-zero exit / spawn failure.
function makeProbe(
  responses: Record<string, string | Error>,
  opts: { origin?: string | Error; official?: boolean; updateBranch?: string } = {}
): InstallStateProbe {
  return {
    git: async (args: string[]) => {
      const key = args.join(' ')
      const v = responses[key]
      if (v instanceof Error) throw v
      if (v === undefined) throw new Error(`unexpected git ${key}`)
      return v
    },
    originUrl: async () => {
      if (opts.origin instanceof Error) throw opts.origin
      return opts.origin ?? 'https://github.com/NousResearch/hermes-agent.git'
    },
    isOfficialUpstream: () => opts.official ?? true,
    updateBranch: opts.updateBranch ?? 'main'
  }
}

const OK_READS: Record<string, string | Error> = {
  'rev-parse --abbrev-ref HEAD': 'main',
  'status --porcelain': '',
  'rev-list origin/main..HEAD --count': '0',
  'rev-list HEAD..origin/main --count': '5'
}

describe('collectInstallState — UNKNOWN != SAFE (git-failure matrix, §5.2A)', () => {
  it('happy path returns a usable InstallState', async () => {
    const r = await collectInstallState(makeProbe({ ...OK_READS }))
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.state.currentBranch).toBe('main')
  })

  it('git unavailable (rev-parse rejects) → !ok', async () => {
    const r = await collectInstallState(makeProbe({ ...OK_READS, 'rev-parse --abbrev-ref HEAD': new Error('git: command not found') }))
    expect(r.ok).toBe(false)
  })

  it('empty branch (broken repo) → !ok', async () => {
    const r = await collectInstallState(makeProbe({ ...OK_READS, 'rev-parse --abbrev-ref HEAD': '' }))
    expect(r.ok).toBe(false)
  })

  it('status read fails → !ok', async () => {
    const r = await collectInstallState(makeProbe({ ...OK_READS, 'status --porcelain': new Error('fatal') }))
    expect(r.ok).toBe(false)
  })

  it('origin missing/unreadable → !ok', async () => {
    const r = await collectInstallState(makeProbe({ ...OK_READS }, { origin: new Error('no origin') }))
    expect(r.ok).toBe(false)
  })

  it('branch/ref missing (rev-list ahead rejects) → !ok', async () => {
    const r = await collectInstallState(
      makeProbe({ ...OK_READS, 'rev-list origin/main..HEAD --count': new Error("fatal: bad revision 'origin/main..HEAD'") })
    )
    expect(r.ok).toBe(false)
  })

  it('ahead count non-numeric (masked ref) → !ok', async () => {
    const r = await collectInstallState(makeProbe({ ...OK_READS, 'rev-list origin/main..HEAD --count': '' }))
    expect(r.ok).toBe(false)
  })

  it('detached HEAD (branch="HEAD") → ok but policy is MANUAL', async () => {
    const r = await collectInstallState(makeProbe({ ...OK_READS, 'rev-parse --abbrev-ref HEAD': 'HEAD' }))
    expect(r.ok).toBe(true)
    if (r.ok) expect(resolveUpdatePolicy(r.state).policy).toBe(UpdatePolicy.MANUAL_REQUIRED)
  })

  it('behind read failing is SAFE → behind=null, still ok (available)', async () => {
    const r = await collectInstallState(makeProbe({ ...OK_READS, 'rev-list HEAD..origin/main --count': new Error('stale') }))
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.state.behind).toBeNull()
  })

  it('CANARY: any failed critical read must make collect !ok (never a benign default)', async () => {
    for (const bad of ['rev-parse --abbrev-ref HEAD', 'status --porcelain', 'rev-list origin/main..HEAD --count']) {
      const r = await collectInstallState(makeProbe({ ...OK_READS, [bad]: new Error('fail') }))
      expect(r.ok).toBe(false)
    }
  })
})

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
