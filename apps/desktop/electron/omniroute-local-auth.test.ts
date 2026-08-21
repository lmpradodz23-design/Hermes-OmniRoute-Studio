import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { DatabaseSync } from 'node:sqlite'

import { test } from 'vitest'

import { ensureOmniRouteLocalToken, revokeOmniRouteLocalToken } from './omniroute-local-auth'

function fixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'hermes-omniroute-token-'))
  const homeDirectory = path.join(root, 'home')
  const userDataDirectory = path.join(root, 'user-data')
  fs.mkdirSync(path.join(homeDirectory, '.omniroute'), { recursive: true })
  const database = new DatabaseSync(path.join(homeDirectory, '.omniroute', 'storage.sqlite'))
  database.exec(`
    CREATE TABLE cli_access_tokens (
      id TEXT PRIMARY KEY,
      token_hash TEXT NOT NULL,
      token_prefix TEXT NOT NULL,
      name TEXT NOT NULL,
      scope TEXT NOT NULL,
      created_at TEXT NOT NULL,
      expires_at TEXT
    )
  `)
  database.close()

  const safeStorageApi = {
    isEncryptionAvailable: () => true,
    encryptString: (value: string) => Buffer.from(`sealed:${value}`, 'utf8'),
    decryptString: (value: Buffer) => value.toString('utf8').replace(/^sealed:/, '')
  }

  return { homeDirectory, root, safeStorageApi, userDataDirectory }
}

test('provisions one encrypted OmniRoute bridge token and reuses its valid database row', () => {
  const value = fixture()

  try {
    const options = {
      ...value,
      now: () => new Date('2026-08-21T12:00:00.000Z'),
      randomBytes: () => Buffer.alloc(32, 7)
    }

    const first = ensureOmniRouteLocalToken(options)
    const second = ensureOmniRouteLocalToken(options)
    assert.equal(second.token, first.token)
    assert.equal(second.id, first.id)

    const store = fs.readFileSync(path.join(value.userDataDirectory, 'omniroute-local-token.json'), 'utf8')
    assert.equal(store.includes(first.token), false, 'plaintext credential must never be persisted')
    assert.match(store, /safeStorage/)

    const database = new DatabaseSync(path.join(value.homeDirectory, '.omniroute', 'storage.sqlite'))

    const rows = database.prepare('SELECT id, scope FROM cli_access_tokens').all() as Array<{
      id: string
      scope: string
    }>

    database.close()
    assert.deepEqual(
      rows.map(row => ({ id: row.id, scope: row.scope })),
      [{ id: first.id, scope: 'admin' }]
    )

    assert.equal(revokeOmniRouteLocalToken(options), true)
    assert.equal(fs.existsSync(path.join(value.userDataDirectory, 'omniroute-local-token.json')), false)
  } finally {
    fs.rmSync(value.root, { recursive: true, force: true })
  }
})

test('fails closed when OS-backed encryption is unavailable', () => {
  const value = fixture()

  try {
    assert.throws(
      () =>
        ensureOmniRouteLocalToken({
          ...value,
          safeStorageApi: { ...value.safeStorageApi, isEncryptionAvailable: () => false }
        }),
      /secure OS token storage is required/i
    )
  } finally {
    fs.rmSync(value.root, { recursive: true, force: true })
  }
})

test('replaces a malformed database hash instead of crashing the desktop', () => {
  const value = fixture()

  try {
    const options = {
      ...value,
      now: () => new Date('2026-08-21T12:00:00.000Z'),
      randomBytes: () => Buffer.alloc(32, 9)
    }

    const first = ensureOmniRouteLocalToken(options)
    const database = new DatabaseSync(path.join(value.homeDirectory, '.omniroute', 'storage.sqlite'))
    database.prepare('UPDATE cli_access_tokens SET token_hash = ? WHERE id = ?').run('bad', first.id)
    database.close()

    const replacement = ensureOmniRouteLocalToken(options)
    assert.notEqual(replacement.id, first.id)

    const verified = new DatabaseSync(path.join(value.homeDirectory, '.omniroute', 'storage.sqlite'))

    const rows = verified.prepare('SELECT id, token_hash FROM cli_access_tokens').all() as Array<{
      id: string
      token_hash: string
    }>

    verified.close()
    assert.equal(rows.length, 1)
    assert.equal(rows[0]?.id, replacement.id)
    assert.match(rows[0]?.token_hash ?? '', /^[0-9a-f]{64}$/)
  } finally {
    fs.rmSync(value.root, { recursive: true, force: true })
  }
})
