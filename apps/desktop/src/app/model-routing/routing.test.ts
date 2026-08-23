import { describe, expect, it } from 'vitest'

import {
  deriveRoutingLabel,
  isLocalProvider,
  RoutingMode,
  type RoutingStatus,
  type RoutingStatusTransport,
  RoutingStatusKind
} from './routing'

function status(over: Partial<RoutingStatus>): RoutingStatus {
  return {
    requestedMode: RoutingMode.AUTO,
    requestedModel: 'auto/coding',
    selectedProvider: 'anthropic',
    selectedModel: 'claude-opus-4-8',
    selectionReason: 'coding preset',
    fallbackUsed: false,
    localOnly: false,
    kind: RoutingStatusKind.RESOLVED,
    ...over
  }
}

describe('deriveRoutingLabel', () => {
  it('auto → resolved cloud model shows "Auto → Claude ..."', () => {
    const l = deriveRoutingLabel(status({}))
    expect(l.prefix).toBe('Auto')
    expect(l.target).toContain('Claude')
    expect(l.blocked).toBe(false)
  })

  it('manual mode is labeled Manual', () => {
    expect(deriveRoutingLabel(status({ requestedMode: RoutingMode.MANUAL })).prefix).toBe('Manual')
  })

  it('local provider is labeled Local with the model id', () => {
    const l = deriveRoutingLabel(status({ selectedProvider: 'ollama', selectedModel: 'qwen2.5-coder' }))
    expect(l.prefix).toBe('Local')
    expect(l.target).toBe('qwen2.5-coder')
  })

  it('fallback is labeled Fallback', () => {
    expect(deriveRoutingLabel(status({ fallbackUsed: true })).prefix).toBe('Fallback')
  })

  it('local-only + cloud provider is BLOCKED, never shown as executable', () => {
    const l = deriveRoutingLabel(status({ localOnly: true, selectedProvider: 'openai', selectedModel: 'gpt-4o' }))
    expect(l.blocked).toBe(true)
    expect(l.prefix).toBe('Bloqueado')
  })

  it('local-only + local provider is fine', () => {
    const l = deriveRoutingLabel(status({ localOnly: true, selectedProvider: 'ollama', selectedModel: 'llama3' }))
    expect(l.blocked).toBe(false)
    expect(l.prefix).toBe('Local')
  })

  it('never invents a model — pending/empty selection yields empty target', () => {
    const l = deriveRoutingLabel(status({ kind: RoutingStatusKind.PENDING, selectedModel: '' }))
    expect(l.target).toBe('')
    expect(l.blocked).toBe(false)
  })

  it('unavailable runtime is blocked with no target', () => {
    const l = deriveRoutingLabel(status({ kind: RoutingStatusKind.UNAVAILABLE }))
    expect(l.blocked).toBe(true)
    expect(l.target).toBe('')
  })
})

describe('isLocalProvider', () => {
  it('recognizes local providers and loopback urls', () => {
    expect(isLocalProvider('ollama')).toBe(true)
    expect(isLocalProvider('lmstudio')).toBe(true)
    expect(isLocalProvider('custom', 'http://127.0.0.1:1234/v1')).toBe(true)
    expect(isLocalProvider('openai', 'https://api.openai.com/v1')).toBe(false)
  })
})

describe('contract (fake transport — not proof of real gateway)', () => {
  it('reflects whatever the runtime reports, unchanged', async () => {
    const fake: RoutingStatusTransport = {
      getRoutingStatus: async () => status({ selectionReason: 'from gateway' })
    }
    const s = await fake.getRoutingStatus('sess-1')
    expect(deriveRoutingLabel(s).prefix).toBe('Auto')
    expect(s.selectionReason).toBe('from gateway')
  })
})
