import { describe, expect, it } from 'vitest'

import { buildGoalInstruction, canGoalTransition, deriveGoalTitle, MAX_GOAL_TITLE } from './goal-authoring'

describe('deriveGoalTitle', () => {
  it('uses the first meaningful line', () => {
    expect(deriveGoalTitle('\n\n  Fix the login bug  \nmore detail')).toBe('Fix the login bug')
  })

  it('returns empty for blank input (never invents a title)', () => {
    expect(deriveGoalTitle('   \n  ')).toBe('')
  })

  it('caps the title length', () => {
    expect(deriveGoalTitle('x'.repeat(MAX_GOAL_TITLE + 50)).length).toBe(MAX_GOAL_TITLE)
  })
})

describe('buildGoalInstruction', () => {
  it('builds a set-goal instruction from the task (reuses agent mechanism)', () => {
    const instr = buildGoalInstruction({ title: 'Ship the U1 context panel', sourceSessionId: 's', sourceProject: 'p' })
    expect(instr).toBe('Set a goal for this task: Ship the U1 context panel')
  })

  it('returns null when there is nothing to base a goal on', () => {
    expect(buildGoalInstruction({ title: '   ', sourceSessionId: 's', sourceProject: 'p' })).toBeNull()
  })
})

describe('canGoalTransition', () => {
  it('allows active↔waiting↔paused and →done', () => {
    expect(canGoalTransition('active', 'waiting')).toBe(true)
    expect(canGoalTransition('waiting', 'active')).toBe(true)
    expect(canGoalTransition('paused', 'done')).toBe(true)
  })

  it('treats done as terminal (no COMPLETED reversal without a new goal)', () => {
    expect(canGoalTransition('done', 'active')).toBe(false)
  })

  it('is idempotent for same-status', () => {
    expect(canGoalTransition('active', 'active')).toBe(true)
  })
})
