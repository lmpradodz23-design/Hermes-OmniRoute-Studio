import { describe, expect, it } from 'vitest'

import { type InstallState, isOfficialUpstream, resolveUpdatePolicy, UpdatePolicy } from './update-policy'

function official(over: Partial<InstallState> = {}): InstallState {
  return {
    currentBranch: 'main',
    updateBranch: 'main',
    behind: 5,
    ahead: 0,
    dirty: false,
    remoteIsOfficialUpstream: true,
    ...over
  }
}

describe('resolveUpdatePolicy — fork guard (P0 root cause)', () => {
  it('A. a fork 370 behind main does NOT auto-update; backend can start', () => {
    const d = resolveUpdatePolicy(
      official({ currentBranch: 'feature/hermes-omniroute-studio', updateBranch: 'main', behind: 370 })
    )
    expect(d.policy).toBe(UpdatePolicy.MANUAL_REQUIRED)
    expect(d.autoUpdateAllowed).toBe(false)
    expect(d.reasons.join(' ')).toContain('feature/hermes-omniroute-studio')
  })

  it('F. a dirty working tree blocks auto-update', () => {
    const d = resolveUpdatePolicy(official({ dirty: true }))
    expect(d.policy).toBe(UpdatePolicy.MANUAL_REQUIRED)
    expect(d.autoUpdateAllowed).toBe(false)
  })

  it('G. local commits ahead block auto-update', () => {
    const d = resolveUpdatePolicy(official({ ahead: 3 }))
    expect(d.policy).toBe(UpdatePolicy.MANUAL_REQUIRED)
    expect(d.autoUpdateAllowed).toBe(false)
  })

  it('a non-official remote (fork origin) blocks auto-update', () => {
    const d = resolveUpdatePolicy(official({ remoteIsOfficialUpstream: false }))
    expect(d.policy).toBe(UpdatePolicy.MANUAL_REQUIRED)
    expect(d.autoUpdateAllowed).toBe(false)
  })

  it('H. a clean official checkout on the update branch, behind, DOES auto-update', () => {
    const d = resolveUpdatePolicy(official({ behind: 5 }))
    expect(d.policy).toBe(UpdatePolicy.AUTO)
    expect(d.autoUpdateAllowed).toBe(true)
  })

  it('behind unknown (null) on a clean official checkout is still auto-updatable', () => {
    const d = resolveUpdatePolicy(official({ behind: null }))
    expect(d.policy).toBe(UpdatePolicy.AUTO)
  })

  it('up-to-date official checkout does nothing', () => {
    const d = resolveUpdatePolicy(official({ behind: 0 }))
    expect(d.policy).toBe(UpdatePolicy.UP_TO_DATE)
    expect(d.autoUpdateAllowed).toBe(false)
  })

  // --- Fail-open hardening (audit P1): unknown != safe ---
  // Before the fix, an empty currentBranch (a failed `git rev-parse`) skipped the
  // branch-mismatch check, so an otherwise-official/clean/ahead-0 state resolved
  // to AUTO — a git-read anomaly could auto-update and clobber a custom checkout.
  it('J. an UNKNOWN current branch (failed git read) does NOT auto-update (unknown != safe)', () => {
    const d = resolveUpdatePolicy(official({ currentBranch: '', behind: 5 }))
    expect(d.policy).toBe(UpdatePolicy.MANUAL_REQUIRED)
    expect(d.autoUpdateAllowed).toBe(false)
    expect(d.reasons.join(' ')).toContain('desconhecido')
  })

  it('K. an UNKNOWN update branch also forces manual (cannot confirm tracked branch)', () => {
    const d = resolveUpdatePolicy(official({ updateBranch: '', behind: 5 }))
    expect(d.policy).toBe(UpdatePolicy.MANUAL_REQUIRED)
    expect(d.autoUpdateAllowed).toBe(false)
  })

  // Canary: this MUST fail if the unknown-branch guard is removed from
  // resolveUpdatePolicy. It pins that a blank branch can never be AUTO.
  it('CANARY: blank branch is never AUTO', () => {
    expect(resolveUpdatePolicy(official({ currentBranch: '' })).policy).not.toBe(UpdatePolicy.AUTO)
    expect(resolveUpdatePolicy(official({ updateBranch: '' })).policy).not.toBe(UpdatePolicy.AUTO)
  })

  it('collects every reason when several fork signals combine', () => {
    const d = resolveUpdatePolicy(
      official({ currentBranch: 'fork', updateBranch: 'main', dirty: true, ahead: 2, remoteIsOfficialUpstream: false })
    )
    expect(d.reasons.length).toBe(4)
  })
})

describe('isOfficialUpstream', () => {
  it('recognizes the official upstream (https/ssh, with/without .git)', () => {
    expect(isOfficialUpstream('https://github.com/NousResearch/hermes-agent')).toBe(true)
    expect(isOfficialUpstream('https://github.com/NousResearch/hermes-agent.git')).toBe(true)
    expect(isOfficialUpstream('git@github.com:NousResearch/hermes-agent.git')).toBe(true)
  })

  it('treats a fork or unknown remote as NOT official (fails closed)', () => {
    expect(isOfficialUpstream('https://github.com/lmprado/hermes-omniroute.git')).toBe(false)
    expect(isOfficialUpstream('https://github.com/NousResearch/other-repo')).toBe(false)
    expect(isOfficialUpstream('')).toBe(false)
    expect(isOfficialUpstream('not a url')).toBe(false)
  })
})
