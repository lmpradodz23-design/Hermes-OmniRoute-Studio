import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import crypto from 'node:crypto'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { test } from 'vitest'

import { requireLocalToken, verifyOmniRouteEndpoint } from '../../../integrations/omniroute-mcp-bridge.mjs'
import { resolveTrustedOmniRouteRoot } from '../../../integrations/omniroute-mcp-policy.mjs'

import {
  DEFAULT_OMNIROUTE_MCP_SCOPES,
  externalFileBlockReason,
  isUnsafeBroadFsRoot,
  resolveAllowedFsIpcPath
} from './security-boundaries'

test('OmniRoute bridge requires a dedicated local token and rejects generic API-key fallback', () => {
  assert.throws(() => requireLocalToken({}), /OMNIROUTE_MCP_TOKEN is required/i)
  assert.throws(
    () => requireLocalToken({ OMNIROUTE_API_KEY: `oma_live_${'a'.repeat(32)}` }),
    /OMNIROUTE_MCP_TOKEN is required/i
  )
  assert.equal(requireLocalToken({ OMNIROUTE_MCP_TOKEN: `oma_live_${'a'.repeat(32)}` }), `oma_live_${'a'.repeat(32)}`)
})

test('OmniRoute endpoint identity must match the trusted installed package version', async () => {
  const response = (
    version: string,
    names = ['omniroute_get_health', 'omniroute_list_models_catalog', 'omniroute_route_request']
  ) =>
    ({
      headers: { get: (name: string) => (name === 'x-omniroute-version' ? version : null) },
      ok: true,
      status: 200,
      json: async () => ({ tools: names.map(name => ({ name, scopes: ['read:health'] })) })
    }) as Response

  await assert.rejects(
    verifyOmniRouteEndpoint(new URL('http://127.0.0.1:20128'), `oma_live_${'a'.repeat(32)}`, '3.8.49', async () =>
      response('9.9.9')
    ),
    /identity mismatch/i
  )

  const payload = await verifyOmniRouteEndpoint(
    new URL('http://127.0.0.1:20128'),
    `oma_live_${'a'.repeat(32)}`,
    '3.8.49',
    async () => response('3.8.49')
  )

  assert.equal(payload.verifiedPackageVersion, '3.8.49')
})

test('default OmniRoute MCP scopes are minimal and never auto-grant privileged writes', () => {
  assert.deepEqual(DEFAULT_OMNIROUTE_MCP_SCOPES, [
    'execute:completions',
    'read:combos',
    'read:health',
    'read:models',
    'read:quota',
    'read:usage'
  ])
  assert.equal(DEFAULT_OMNIROUTE_MCP_SCOPES.includes('write:plugins' as never), false)
  assert.equal(DEFAULT_OMNIROUTE_MCP_SCOPES.includes('write:budget' as never), false)
})

test('external file policy rejects executables and sensitive files', () => {
  assert.match(String(externalFileBlockReason('C:\\Windows\\System32\\calc.exe')), /executable/i)
  for (const extension of [
    '.hta',
    '.wsf',
    '.wsh',
    '.jse',
    '.vbe',
    '.reg',
    '.url',
    '.scf',
    '.pif',
    '.cpl',
    '.msc',
    '.msp',
    '.appref-ms',
    '.ps2',
    '.psc1',
    '.chm',
    '.sct',
    '.inf'
  ]) {
    assert.match(String(externalFileBlockReason(`C:\\Temp\\payload${extension}`)), /executable/i, extension)
  }
  assert.match(String(externalFileBlockReason(path.join(os.homedir(), '.ssh', 'id_rsa'))), /sensitive/i)
  assert.equal(externalFileBlockReason(path.join(os.tmpdir(), 'report.pdf')), null)
})

test('filesystem IPC writes are confined to explicitly allowed roots', () => {
  const root = path.join(os.tmpdir(), 'hermes-project')

  assert.equal(resolveAllowedFsIpcPath(path.join(root, 'IDEA.md'), [root]), path.resolve(root, 'IDEA.md'))
  assert.throws(
    () => resolveAllowedFsIpcPath(path.join(os.tmpdir(), 'outside', 'payload.cmd'), [root]),
    /outside the allowed roots/i
  )
})

test('native file grants are exact and never grant the selected parent directory', () => {
  const root = path.join(os.tmpdir(), 'hermes-native-selection')
  const selected = path.join(root, 'selected.txt')
  const sibling = path.join(root, 'sibling.txt')

  assert.equal(resolveAllowedFsIpcPath(selected, [], [selected]), path.resolve(selected))
  assert.throws(() => resolveAllowedFsIpcPath(sibling, [], [selected]), /outside the allowed roots/i)
})

test('drive roots and the user home are rejected as broad grants', () => {
  assert.equal(isUnsafeBroadFsRoot('C:\\'), true)
  assert.equal(isUnsafeBroadFsRoot('/', '/home/example'), true)
  assert.equal(isUnsafeBroadFsRoot('/home/example', '/home/example'), true)
  assert.equal(isUnsafeBroadFsRoot('/home/example/project', '/home/example'), false)
})

test('OmniRoute bridge rejects an environment-controlled package root outside its allowlist', async () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'hermes-omniroute-root-'))
  const allowed = path.join(temp, 'trusted')
  const attacker = path.join(temp, 'attacker')

  try {
    for (const root of [allowed, attacker]) {
      fs.mkdirSync(path.join(root, 'dist', 'open-sse', 'mcp-server'), { recursive: true })
      fs.writeFileSync(
        path.join(root, 'package.json'),
        JSON.stringify({ name: 'omniroute', version: '3.8.49' }),
        'utf8'
      )
      fs.writeFileSync(path.join(root, 'dist', 'open-sse', 'mcp-server', 'server.js'), 'export {}', 'utf8')
    }

    await assert.rejects(
      resolveTrustedOmniRouteRoot({
        requestedRoot: attacker,
        allowedRoots: [allowed],
        capabilitiesLockPath: path.join(temp, 'missing.lock')
      }),
      /not in the trusted install roots/i
    )
    assert.equal(
      await resolveTrustedOmniRouteRoot({
        requestedRoot: allowed,
        allowedRoots: [allowed],
        capabilitiesLockPath: path.join(temp, 'missing.lock')
      }),
      await fs.promises.realpath(allowed)
    )
  } finally {
    fs.rmSync(temp, { recursive: true, force: true })
  }
})

test('OmniRoute server.js byte drift is blocked by the capability lock', async () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'hermes-omniroute-lock-'))
  const root = path.join(temp, 'trusted')
  const server = path.join(root, 'dist', 'open-sse', 'mcp-server', 'server.js')
  const lockPath = path.join(temp, 'capabilities.lock')
  try {
    fs.mkdirSync(path.dirname(server), { recursive: true })
    fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ name: 'omniroute', version: '3.8.49' }), 'utf8')
    fs.writeFileSync(server, 'export {}', 'utf8')
    const serverHash = crypto
      .createHash('sha256')
      .update(fs.readFileSync(server))
      .digest('hex')
    fs.writeFileSync(
      lockPath,
      JSON.stringify({
        version: 1,
        skills: [],
        plugins: [],
        mcp_servers: [{ id: 'omniroute', version: '3.8.49', server_sha256: serverHash }]
      }),
      'utf8'
    )
    assert.equal(
      await resolveTrustedOmniRouteRoot({
        requestedRoot: root,
        allowedRoots: [root],
        capabilitiesLockPath: lockPath
      }),
      await fs.promises.realpath(root)
    )
    fs.appendFileSync(server, 'x', 'utf8')
    await assert.rejects(
      resolveTrustedOmniRouteRoot({
        requestedRoot: root,
        allowedRoots: [root],
        capabilitiesLockPath: lockPath
      }),
      /server\.js hash mismatch/i
    )
  } finally {
    fs.rmSync(temp, { recursive: true, force: true })
  }
})

// This is a live integration test: it writes a scoped CLI token into the
// real OmniRoute SQLite store and drives the actual bridge over stdio. A
// machine without OmniRoute installed has nothing to integrate with, so it
// declares a named skip instead of failing red for the wrong reason.
const OMNIROUTE_STORAGE = path.join(os.homedir(), '.omniroute', 'storage.sqlite')
const HAS_OMNIROUTE_STORAGE = fs.existsSync(OMNIROUTE_STORAGE)

test.skipIf(!HAS_OMNIROUTE_STORAGE)(
  'real MCP bridge exposes privileged tools but denies their missing write scopes (needs a local OmniRoute install)',
  async () => {
  const { DatabaseSync } = await import('node:sqlite')
  const databasePath = OMNIROUTE_STORAGE
  const database = new DatabaseSync(databasePath)
  const keyId = `tok_${crypto.randomUUID()}`
  const key = `oma_live_${crypto.randomBytes(32).toString('base64url')}`
  const now = new Date().toISOString()
  database
    .prepare(
      'INSERT INTO cli_access_tokens (id, token_hash, token_prefix, name, scope, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)'
    )
    .run(
      keyId,
      crypto.createHash('sha256').update(key).digest('hex'),
      key.slice(0, 15),
      'Hermes MCP security test',
      'admin',
      now,
      null
    )
  const bridgePath = fileURLToPath(new URL('../../../integrations/omniroute-mcp-bridge.mjs', import.meta.url))

  const child = spawn(process.execPath, [bridgePath], {
    env: {
      ...process.env,
      OMNIROUTE_MCP_ENFORCE_SCOPES: 'true',
      OMNIROUTE_MCP_SCOPES: DEFAULT_OMNIROUTE_MCP_SCOPES.join(','),
      OMNIROUTE_MCP_TOKEN: key
    },
    stdio: ['pipe', 'pipe', 'pipe'],
    windowsHide: true
  })

  let stdout = ''
  let stderr = ''
  child.stdout.setEncoding('utf8')
  child.stderr.setEncoding('utf8')
  child.stdout.on('data', chunk => {
    stdout += chunk
  })
  child.stderr.on('data', chunk => {
    stderr += chunk
  })

  const send = (message: unknown) => child.stdin.write(`${JSON.stringify(message)}\n`)

  const waitForResponse = (id: number) =>
    new Promise<any>((resolve, reject) => {
      const started = Date.now()

      const poll = () => {
        for (const line of stdout.split(/\r?\n/)) {
          if (!line.trim()) {
            continue
          }

          try {
            const parsed = JSON.parse(line)

            if (parsed.id === id) {
              return resolve(parsed)
            }
          } catch {
            // Startup diagnostics are expected on stderr, but ignore any
            // non-protocol stdout defensively while waiting for the response.
          }
        }

        if (child.exitCode !== null) {
          return reject(new Error(`MCP bridge exited ${child.exitCode}: ${stderr}`))
        }

        if (Date.now() - started > 20_000) {
          return reject(new Error(`Timed out waiting for MCP response ${id}: ${stderr}`))
        }

        setTimeout(poll, 25)
      }

      poll()
    })

  try {
    send({
      jsonrpc: '2.0',
      id: 1,
      method: 'initialize',
      params: {
        protocolVersion: '2024-11-05',
        capabilities: {},
        clientInfo: { name: 'hermes-security-test', version: '1.0.0' }
      }
    })
    const initialized = await waitForResponse(1)
    assert.equal(initialized.error, undefined)
    send({ jsonrpc: '2.0', method: 'notifications/initialized', params: {} })
    send({ jsonrpc: '2.0', id: 2, method: 'tools/list', params: {} })
    const listed = await waitForResponse(2)
    assert.equal(listed.error, undefined)
    assert.equal(
      listed.result?.tools?.some((tool: { name?: string }) => tool.name === 'plugin_install'),
      true,
      'scope enforcement must not hide tools from the explicit-consent UI'
    )
    send({
      jsonrpc: '2.0',
      id: 3,
      method: 'tools/call',
      params: { name: 'plugin_install', arguments: { path: path.resolve('never-executed') } }
    })
    const denied = await waitForResponse(3)
    assert.equal(denied.result?.isError, true)
    assert.match(JSON.stringify(denied.result), /missing_scopes/i)
    assert.match(JSON.stringify(denied.result), /write:plugins/i)
    assert.equal(
      listed.result?.tools?.some((tool: { name?: string }) => tool.name === 'omniroute_set_budget_guard'),
      true,
      'budget controls remain visible for an explicit user scope grant'
    )
    send({
      jsonrpc: '2.0',
      id: 4,
      method: 'tools/call',
      params: {
        name: 'omniroute_set_budget_guard',
        arguments: { budgetUsd: 999, action: 'warn' }
      }
    })
    const budgetDenied = await waitForResponse(4)
    assert.equal(budgetDenied.result?.isError, true)
    assert.match(JSON.stringify(budgetDenied.result), /missing_scopes/i)
    assert.match(JSON.stringify(budgetDenied.result), /write:budget/i)
  } finally {
    child.stdin.end()
    child.kill()
    database.prepare('DELETE FROM cli_access_tokens WHERE id = ?').run(keyId)
    database.close()
  }
  },
  30_000
)
