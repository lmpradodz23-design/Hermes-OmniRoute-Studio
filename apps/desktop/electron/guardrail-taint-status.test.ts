import assert from 'node:assert/strict'
import crypto from 'node:crypto'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { afterEach, test } from 'vitest'

import { readGuardrailTaintStatus } from './guardrail-taint-status'

const roots: string[] = []

afterEach(() => {
  for (const root of roots.splice(0)) fs.rmSync(root, { force: true, recursive: true })
})

function fixture(sessionId: string, value: unknown): string {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'hermes-taint-status-'))
  roots.push(root)
  const digest = crypto.createHash('sha256').update(sessionId, 'utf8').digest('hex')
  const destination = path.join(root, 'runtime', 'guardrail-taint', `${digest}.json`)
  fs.mkdirSync(path.dirname(destination), { recursive: true })
  fs.writeFileSync(destination, JSON.stringify(value), 'utf8')
  return root
}

test('reads only the fixed redacted taint status schema', () => {
  const root = fixture('session-a', {
    active: true,
    at: '2026-08-21T10:00:00Z',
    detail: 'https://example.test/reference',
    source: 'web',
    turns_ago: 2,
    ignored: 'not exposed'
  })

  assert.deepEqual(readGuardrailTaintStatus(root, 'session-a'), {
    active: true,
    at: '2026-08-21T10:00:00Z',
    detail: 'https://example.test/reference',
    source: 'web',
    turnsAgo: 2
  })
})

test('fails closed to inactive for invalid ids, sources, and malformed files', () => {
  const invalidSource = fixture('session-b', { active: true, source: 'system', turns_ago: 0 })
  const malformed = fixture('session-c', '{not-json')

  assert.equal(readGuardrailTaintStatus(invalidSource, 'session-b').active, false)
  assert.equal(readGuardrailTaintStatus(malformed, 'session-c').active, false)
  assert.equal(readGuardrailTaintStatus(invalidSource, '../session-b').active, false)
  assert.equal(readGuardrailTaintStatus(invalidSource, 'x'.repeat(257)).active, false)
})
