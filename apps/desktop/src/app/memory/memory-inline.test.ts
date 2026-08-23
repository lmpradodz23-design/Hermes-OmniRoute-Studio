import { describe, expect, it } from 'vitest'

import { memoryAffordances } from './memory-inline'

describe('memoryAffordances', () => {
  it('shows enabled indicator + count + forget when enabled, remembered, and forgettable', () => {
    const a = memoryAffordances({ enabled: true, rememberedCount: 5, canForget: true })
    expect(a).toEqual({
      showEnabledIndicator: true,
      showRememberedCount: true,
      showOpenStarmap: true,
      showForget: true
    })
  })

  it('hides count and forget when nothing is remembered', () => {
    const a = memoryAffordances({ enabled: true, rememberedCount: 0, canForget: true })
    expect(a.showRememberedCount).toBe(false)
    expect(a.showForget).toBe(false)
  })

  it('never shows forget when the provider does not support it', () => {
    const a = memoryAffordances({ enabled: true, rememberedCount: 9, canForget: false })
    expect(a.showForget).toBe(false)
  })

  it('when memory is off, only "open starmap" remains', () => {
    const a = memoryAffordances({ enabled: false, rememberedCount: 3, canForget: true })
    expect(a).toEqual({
      showEnabledIndicator: false,
      showRememberedCount: false,
      showOpenStarmap: true,
      showForget: false
    })
  })
})
