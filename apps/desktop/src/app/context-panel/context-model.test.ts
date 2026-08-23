import { describe, expect, it } from 'vitest'

import {
  ContextSecurity,
  ContextTab,
  deriveContextSecurity,
  deriveContextSnapshot,
  type PanelContent,
  resolveActiveTab,
  visibleTabs
} from './context-model'

const EMPTY: PanelContent = {
  hasFiles: false,
  artifactCount: 0,
  changedFileCount: 0,
  hasPreview: false,
  hasProject: false,
  activeToolCount: 0
}

describe('visibleTabs', () => {
  it('shows nothing when there is no content (no empty tabs)', () => {
    expect(visibleTabs(EMPTY)).toEqual([])
  })

  it('shows only tabs with real content, in canonical order', () => {
    const tabs = visibleTabs({ ...EMPTY, hasFiles: true, changedFileCount: 3, hasProject: true })
    expect(tabs).toEqual([ContextTab.FILES, ContextTab.CHANGES, ContextTab.CONTEXT])
  })

  it('hides changes when zero changed files (no fake diff tab)', () => {
    expect(visibleTabs({ ...EMPTY, artifactCount: 2 })).toEqual([ContextTab.ARTIFACTS])
  })

  it('shows all tabs when everything has content', () => {
    const tabs = visibleTabs({
      hasFiles: true,
      artifactCount: 1,
      changedFileCount: 1,
      hasPreview: true,
      hasProject: true,
      activeToolCount: 1
    })
    expect(tabs).toHaveLength(6)
  })
})

describe('resolveActiveTab (session/project switch)', () => {
  it('keeps the current tab when still visible', () => {
    expect(resolveActiveTab(ContextTab.CHANGES, [ContextTab.FILES, ContextTab.CHANGES])).toBe(ContextTab.CHANGES)
  })

  it('falls back to the first visible tab when the current one disappears', () => {
    expect(resolveActiveTab(ContextTab.CHANGES, [ContextTab.FILES])).toBe(ContextTab.FILES)
  })

  it('returns null when nothing is visible', () => {
    expect(resolveActiveTab(ContextTab.FILES, [])).toBeNull()
  })
})

describe('context security tri-state', () => {
  it('local-only wins over everything', () => {
    expect(deriveContextSecurity({ localOnly: true, redactBeforeCloud: true })).toBe(ContextSecurity.LOCAL_ONLY)
  })

  it('redact-before-cloud when not local-only', () => {
    expect(deriveContextSecurity({ localOnly: false, redactBeforeCloud: true })).toBe(ContextSecurity.REDACTED)
  })

  it('cloud allowed as the open default', () => {
    expect(deriveContextSecurity({ localOnly: false, redactBeforeCloud: false })).toBe(ContextSecurity.CLOUD_ALLOWED)
  })
})

describe('deriveContextSnapshot', () => {
  it('never invents fields — absent values are empty/zero', () => {
    const snap = deriveContextSnapshot({ security: { localOnly: false, redactBeforeCloud: false } })
    expect(snap.project).toBe('')
    expect(snap.fileCount).toBe(0)
    expect(snap.goalTitle).toBeNull()
    expect(snap.memoryEnabled).toBe(false)
    expect(snap.security).toBe(ContextSecurity.CLOUD_ALLOWED)
  })

  it('reflects the real active context', () => {
    const snap = deriveContextSnapshot({
      project: 'hermes',
      cwd: '/proj',
      fileCount: 12,
      memoryEnabled: true,
      goalTitle: 'Ship U1',
      model: 'claude-opus',
      security: { localOnly: true, redactBeforeCloud: false }
    })
    expect(snap.project).toBe('hermes')
    expect(snap.goalTitle).toBe('Ship U1')
    expect(snap.security).toBe(ContextSecurity.LOCAL_ONLY)
  })
})
