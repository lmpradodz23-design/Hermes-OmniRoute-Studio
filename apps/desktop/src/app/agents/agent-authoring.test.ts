import { describe, expect, it } from 'vitest'

import {
  AgentActionDecision,
  AgentActionKind,
  decideAgentAction,
  MAX_AGENT_NAME,
  validateAgentDraft
} from './agent-authoring'

const okDraft = { name: 'Reviewer', instructions: 'review code', tools: [] }

describe('validateAgentDraft', () => {
  it('accepts a valid draft', () => {
    expect(validateAgentDraft(okDraft)).toEqual([])
  })

  it('requires a name', () => {
    expect(validateAgentDraft({ ...okDraft, name: '  ' })[0].field).toBe('name')
  })

  it('bounds name length', () => {
    expect(validateAgentDraft({ ...okDraft, name: 'x'.repeat(MAX_AGENT_NAME + 1) })[0].field).toBe('name')
  })
})

describe('decideAgentAction', () => {
  it('allows read-only actions without a gateway', () => {
    expect(decideAgentAction(AgentActionKind.SELECT, { hasGateway: false, capabilityGranted: false })).toBe(
      AgentActionDecision.ALLOW
    )
    expect(decideAgentAction(AgentActionKind.VIEW, { hasGateway: false, capabilityGranted: false })).toBe(
      AgentActionDecision.ALLOW
    )
  })

  it('denies mutating actions without capability', () => {
    expect(decideAgentAction(AgentActionKind.DELEGATE, { hasGateway: true, capabilityGranted: false })).toBe(
      AgentActionDecision.DENIED_CAPABILITY
    )
  })

  it('blocks mutating actions when the gateway is down (real reason, not a fake button)', () => {
    expect(decideAgentAction(AgentActionKind.CREATE, { hasGateway: false, capabilityGranted: true, draft: okDraft })).toBe(
      AgentActionDecision.BLOCKED_GATEWAY
    )
  })

  it('rejects an invalid create draft before touching the gateway', () => {
    expect(
      decideAgentAction(AgentActionKind.CREATE, {
        hasGateway: true,
        capabilityGranted: true,
        draft: { name: '', instructions: '', tools: [] }
      })
    ).toBe(AgentActionDecision.INVALID)
  })

  it('allows a valid mutating action with capability + gateway', () => {
    expect(
      decideAgentAction(AgentActionKind.CREATE, { hasGateway: true, capabilityGranted: true, draft: okDraft })
    ).toBe(AgentActionDecision.ALLOW)
  })
})
