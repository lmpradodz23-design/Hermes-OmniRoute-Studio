import assert from 'node:assert/strict'

import { test } from 'vitest'

import { SshConnection } from './ssh-connection'

const host = process.env.HERMES_LIVE_SSH_HOST
const user = process.env.HERMES_LIVE_SSH_USER
const keyPath = process.env.HERMES_LIVE_SSH_KEY
const port = Number(process.env.HERMES_LIVE_SSH_PORT || 0)
const liveConfigured = Boolean(host && user && keyPath && Number.isInteger(port) && port > 0)

test.skipIf(!liveConfigured)('executes a real command through OpenSSH with mux disabled', async () => {
  const connection = new SshConnection(
    { host, keyPath, port, user },
    { connectTimeoutMs: 15_000, execTimeoutMs: 15_000, mux: false }
  )

  try {
    await connection.open()
    assert.equal((await connection.exec('printf HERMES_SSH_LIVE_OK')).trim(), 'HERMES_SSH_LIVE_OK')
    assert.equal(await connection.isAlive(), true)
  } finally {
    await connection.close()
  }
})
