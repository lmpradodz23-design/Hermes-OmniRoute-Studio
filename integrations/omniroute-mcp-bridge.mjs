#!/usr/bin/env node

import { Console } from 'node:console'
import fs from 'node:fs'
import path from 'node:path'
import readline from 'node:readline'
import { fileURLToPath } from 'node:url'

import { resolveTrustedOmniRouteRoot } from './omniroute-mcp-policy.mjs'

const stderrConsole = new Console({ stdout: process.stderr, stderr: process.stderr })
console.log = stderrConsole.log.bind(stderrConsole)
console.warn = stderrConsole.warn.bind(stderrConsole)

export function requireLocalToken(env = process.env) {
  const token = String(env.OMNIROUTE_MCP_TOKEN || '').trim()
  if (!/^oma_live_[A-Za-z0-9_-]{24,}$/.test(token)) {
    throw new Error('A valid OMNIROUTE_MCP_TOKEN is required for the local OmniRoute bridge')
  }
  return token
}

export async function verifyOmniRouteEndpoint(base, apiKey, expectedVersion, fetchImpl = fetch) {
  const response = await fetchImpl(new URL('/api/mcp/tools', base), {
    headers: authenticatedHeaders(apiKey, { accept: 'application/json' }),
    signal: AbortSignal.timeout(10_000)
  })
  if (!response.ok) {
    throw new Error(`Unable to authenticate the local OmniRoute endpoint (HTTP ${response.status})`)
  }
  const payload = await response.json()
  const tools = Array.isArray(payload?.tools) ? payload.tools : []
  const names = new Set(tools.map(tool => tool?.name).filter(name => typeof name === 'string'))
  const identityMarkers = ['omniroute_get_health', 'omniroute_list_models_catalog', 'omniroute_route_request']
  if (!identityMarkers.every(name => names.has(name))) {
    throw new Error('OmniRoute endpoint identity mismatch; authenticated MCP catalog markers are missing')
  }
  const reportedVersion = response.headers?.get?.('x-omniroute-version')?.trim() || ''
  if (reportedVersion && reportedVersion !== expectedVersion) {
    throw new Error(
      `OmniRoute endpoint identity mismatch; expected version ${expectedVersion}, received ${reportedVersion}`
    )
  }
  return { ...payload, verifiedPackageVersion: expectedVersion }
}

function loopbackOmniRouteBase() {
  const configured = String(process.env.OMNIROUTE_BASE_URL || 'http://127.0.0.1:20128').trim()
  const base = new URL(configured)
  if (base.protocol !== 'http:' || !['127.0.0.1', 'localhost', '::1', '[::1]'].includes(base.hostname)) {
    throw new Error('Compression control requires a loopback OmniRoute endpoint')
  }

  return base
}

function parseMcpResponse(response, expectedId) {
  for (const payload of responsePayloads(response.contentType, response.body)) {
    const parsed = JSON.parse(payload)
    if (parsed?.id === expectedId) return parsed
  }

  throw new Error(`OmniRoute MCP response ${expectedId} was missing`)
}

function parseMcpToolResult(message, toolName) {
  if (message?.error) {
    throw new Error(`OmniRoute MCP tool ${toolName} failed: ${message.error.message || 'unknown error'}`)
  }
  const result = message?.result
  if (result?.isError) {
    const detail = result.content?.find?.(entry => entry?.type === 'text')?.text || 'unknown error'
    throw new Error(`OmniRoute MCP tool ${toolName} failed: ${detail}`)
  }
  if (result?.structuredContent && typeof result.structuredContent === 'object') {
    return result.structuredContent
  }
  const text = result?.content?.find?.(entry => entry?.type === 'text')?.text
  if (typeof text !== 'string') {
    throw new Error(`OmniRoute MCP tool ${toolName} returned no structured result`)
  }

  return JSON.parse(text)
}

async function callCompressionTool(toolName, args, apiKey) {
  const endpoint = new URL('/api/mcp/stream', loopbackOmniRouteBase())
  let sessionId = ''

  const post = async message => {
    const headers = authenticatedHeaders(apiKey, {
      accept: 'application/json, text/event-stream',
      'content-type': 'application/json'
    })
    if (sessionId) headers['mcp-session-id'] = sessionId
    const response = await fetch(endpoint, {
      method: 'POST',
      headers,
      body: JSON.stringify(message),
      signal: AbortSignal.timeout(15_000)
    })
    const nextSessionId = response.headers.get('mcp-session-id')
    if (nextSessionId) sessionId = nextSessionId
    const body = await response.text()
    if (!response.ok) {
      throw new Error(`OmniRoute MCP compression transport failed with HTTP ${response.status}: ${body.slice(0, 300)}`)
    }

    return { body, contentType: response.headers.get('content-type') || '' }
  }

  try {
    const initialized = await post({
      jsonrpc: '2.0',
      id: 1,
      method: 'initialize',
      params: {
        protocolVersion: '2024-11-05',
        capabilities: {},
        clientInfo: { name: 'hermes-omniroute-studio', version: '1.0.0' }
      }
    })
    parseMcpResponse(initialized, 1)
    await post({ jsonrpc: '2.0', method: 'notifications/initialized', params: {} })
    const called = await post({
      jsonrpc: '2.0',
      id: 2,
      method: 'tools/call',
      params: {
        name: toolName,
        arguments: args,
        _meta: { omniroute: { scopes: ['read:compression', 'write:compression'] } }
      }
    })

    return parseMcpToolResult(parseMcpResponse(called, 2), toolName)
  } finally {
    if (sessionId) {
      const headers = authenticatedHeaders(apiKey, { 'mcp-session-id': sessionId })
      await fetch(endpoint, { method: 'DELETE', headers, signal: AbortSignal.timeout(5_000) }).catch(() => {})
    }
  }
}

function parseConfiguredScopes() {
  return String(process.env.OMNIROUTE_MCP_SCOPES || '')
    .split(',')
    .map(scope => scope.trim())
    .filter(Boolean)
}

const BUILTIN_TOOL_SCOPES = new Map([
  ['omniroute_set_budget_guard', ['write:budget']],
  ['plugin_list', ['read:plugins']],
  ['plugin_install', ['write:plugins']],
  ['plugin_activate', ['write:plugins']],
  ['plugin_deactivate', ['write:plugins']],
  ['plugin_uninstall', ['write:plugins']],
  ['plugin_configure', ['write:plugins']],
  ['plugin_executions', ['read:plugins']],
  ['plugin_scan', ['write:plugins']]
])

function authenticatedHeaders(apiKey, headers = {}) {
  return apiKey ? { ...headers, authorization: `Bearer ${apiKey}` } : headers
}

async function loadToolScopeCatalog(base, apiKey) {
  const response = await fetch(new URL('/api/mcp/tools', base), {
    headers: authenticatedHeaders(apiKey, { accept: 'application/json' }),
    signal: AbortSignal.timeout(10_000)
  })
  if (!response.ok) {
    throw new Error(`Unable to load the OmniRoute MCP scope catalog (HTTP ${response.status})`)
  }
  const payload = await response.json()
  const tools = Array.isArray(payload?.tools) ? payload.tools : null
  if (!tools) throw new Error('OmniRoute MCP scope catalog returned an invalid payload')

  const catalog = new Map(BUILTIN_TOOL_SCOPES)
  for (const tool of tools) {
    if (!tool || typeof tool.name !== 'string' || !Array.isArray(tool.scopes)) continue
    const scopes = tool.scopes.filter(scope => typeof scope === 'string' && scope.trim())
    if (scopes.length > 0) catalog.set(tool.name, scopes)
  }
  return catalog
}

function deniedToolCall(message, reason, details) {
  return {
    jsonrpc: '2.0',
    id: message.id,
    result: {
      content: [{ type: 'text', text: JSON.stringify({ allowed: false, reason, ...details }) }],
      isError: true
    }
  }
}

export function authorizeToolCall(message, catalog, configuredScopes) {
  if (!message || message.method !== 'tools/call') return null
  const tool = message.params?.name
  if (typeof tool !== 'string' || !tool.trim()) {
    return deniedToolCall(message, 'invalid_tool_name', { tool: null })
  }
  const required = catalog.get(tool)
  if (!required) {
    return deniedToolCall(message, 'tool_definition_missing', {
      tool,
      required: [],
      provided: configuredScopes
    })
  }
  const allowed = new Set(configuredScopes)
  const missing = required.filter(scope => !allowed.has(scope))
  if (missing.length === 0) return null
  return deniedToolCall(message, 'missing_scopes', {
    tool,
    required,
    provided: configuredScopes,
    missing
  })
}

function applyBridgeScopeBoundary(message) {
  if (!message || message.method !== 'tools/call' || !message.params || typeof message.params !== 'object') {
    return message
  }
  const existingMeta =
    message.params._meta && typeof message.params._meta === 'object' ? message.params._meta : {}
  return {
    ...message,
    params: {
      ...message.params,
      _meta: {
        ...existingMeta,
        scopes: undefined,
        auth: undefined,
        omniroute: { scopes: parseConfiguredScopes() }
      }
    }
  }
}

function responsePayloads(contentType, body) {
  if (!body.trim()) return []
  if (!contentType.toLowerCase().includes('text/event-stream')) return [body.trim()]
  return body
    .split(/\r?\n/)
    .filter(line => line.startsWith('data:'))
    .map(line => line.slice('data:'.length).trim())
    .filter(payload => payload && payload !== '[DONE]')
}

async function startHttpMcpProxy(apiKey) {
  const configured = String(process.env.OMNIROUTE_BASE_URL || 'http://127.0.0.1:20128').trim()
  const base = new URL(configured)
  if (base.protocol !== 'http:' || !['127.0.0.1', 'localhost', '::1', '[::1]'].includes(base.hostname)) {
    throw new Error('MCP bridge requires a loopback OmniRoute endpoint')
  }
  const endpoint = new URL('/api/mcp/stream', base)
  let sessionId = ''
  const configuredScopes = parseConfiguredScopes()
  const enforceScopes = process.env.OMNIROUTE_MCP_ENFORCE_SCOPES !== 'false'
  const toolScopeCatalog = enforceScopes ? await loadToolScopeCatalog(base, apiKey) : new Map()

  const forward = async rawLine => {
    if (!rawLine.trim()) return
    let message
    try {
      message = applyBridgeScopeBoundary(JSON.parse(rawLine))
    } catch {
      throw new Error('Invalid JSON-RPC message received on MCP stdio')
    }
    if (enforceScopes) {
      const denial = authorizeToolCall(message, toolScopeCatalog, configuredScopes)
      if (denial) {
        process.stdout.write(`${JSON.stringify(denial)}\n`)
        return
      }
    }
    const headers = {
      accept: 'application/json, text/event-stream',
      'content-type': 'application/json'
    }
    if (sessionId) headers['mcp-session-id'] = sessionId
    if (apiKey) headers.authorization = `Bearer ${apiKey}`
    const response = await fetch(endpoint, {
      method: 'POST',
      headers,
      body: JSON.stringify(message),
      signal: AbortSignal.timeout(30_000)
    })
    const nextSessionId = response.headers.get('mcp-session-id')
    if (nextSessionId) sessionId = nextSessionId
    const body = await response.text()
    if (!response.ok) {
      throw new Error(`OmniRoute MCP HTTP transport failed with HTTP ${response.status}: ${body.slice(0, 300)}`)
    }
    for (const payload of responsePayloads(response.headers.get('content-type') || '', body)) {
      process.stdout.write(`${payload}\n`)
    }
  }

  const lines = readline.createInterface({ input: process.stdin, crlfDelay: Infinity, terminal: false })
  let queue = Promise.resolve()
  lines.on('line', line => {
    queue = queue.then(() => forward(line)).catch(error => {
      console.error(`[omniroute-mcp-bridge] ${error.message}`)
      process.exitCode = 1
      lines.close()
    })
  })
  await new Promise(resolve => lines.once('close', resolve))
  await queue

  if (sessionId) {
    const headers = { 'mcp-session-id': sessionId }
    if (apiKey) headers.authorization = `Bearer ${apiKey}`
    await fetch(endpoint, { method: 'DELETE', headers, signal: AbortSignal.timeout(5_000) }).catch(() => {})
  }
}

export async function runBridge(argv = process.argv.slice(2)) {
  // Every bridge operation is authenticated. Loopback-only is not an identity
  // boundary: an unrelated local process can bind the same port.
  const apiKey = requireLocalToken()
  const requestedRoot = process.env.OMNIROUTE_BRIDGE_DEV_MODE === 'true' ? process.env.OMNIROUTE_PACKAGE_ROOT : undefined
  const packageRoot = await resolveTrustedOmniRouteRoot({ requestedRoot })
  const packageJson = JSON.parse(await fs.promises.readFile(path.join(packageRoot, 'package.json'), 'utf8'))
  const configured = String(process.env.OMNIROUTE_BASE_URL || 'http://127.0.0.1:20128').trim()
  const base = new URL(configured)
  if (base.protocol !== 'http:' || !['127.0.0.1', 'localhost', '::1', '[::1]'].includes(base.hostname)) {
    throw new Error('OmniRoute bridge requires a loopback endpoint')
  }
  await verifyOmniRouteEndpoint(base, apiKey, String(packageJson.version || ''))

  const command = argv[0]
  if (command === '--compression-status' || command === '--compression-set') {
    const mode = argv[1]
    if (command === '--compression-set' && mode !== 'caveman' && mode !== 'off') {
      throw new Error('Unsupported compression mode; expected caveman or off')
    }
    const result =
      command === '--compression-status'
        ? await callCompressionTool('omniroute_compression_status', {}, apiKey)
        : await callCompressionTool('omniroute_set_compression_engine', { engine: mode }, apiKey)
    process.stdout.write(`${JSON.stringify(result)}\n`)
    return
  }

  // Production never trusts a package root inherited from the user's shell.
  // A source checkout may opt into an alternate root, but it still has to
  // resolve to one of the install locations accepted by the policy module.
  await startHttpMcpProxy(apiKey)
}

const invokedPath = process.argv[1] ? path.resolve(process.argv[1]) : ''
if (invokedPath && invokedPath === path.resolve(fileURLToPath(import.meta.url))) {
  await runBridge()
}
