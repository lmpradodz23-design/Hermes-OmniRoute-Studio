import fs from 'node:fs'
import crypto from 'node:crypto'
import os from 'node:os'
import path from 'node:path'

export const MINIMUM_OMNIROUTE_VERSION = '3.8.49'
export const MAXIMUM_OMNIROUTE_MAJOR = 3

async function sha256File(filePath) {
  const bytes = await fs.promises.readFile(filePath)
  return crypto.createHash('sha256').update(bytes).digest('hex')
}

function defaultCapabilitiesLockPath() {
  const configured = String(process.env.HERMES_HOME || '').trim()
  if (configured) return path.join(configured, 'capabilities.lock')
  if (process.platform === 'win32') {
    const localAppData = String(process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local'))
    return path.join(localAppData, 'hermes', 'capabilities.lock')
  }
  return path.join(os.homedir(), '.hermes', 'capabilities.lock')
}

export async function verifyLockedOmniRouteServer(serverPath, packageVersion, lockFile = defaultCapabilitiesLockPath()) {
  let raw
  try {
    raw = await fs.promises.readFile(lockFile, 'utf8')
  } catch (error) {
    if (error?.code === 'ENOENT') return
    throw new Error(`Unable to read Hermes capability lock: ${error.message}`)
  }
  let lock
  try {
    lock = JSON.parse(raw)
  } catch (error) {
    throw new Error(`Invalid Hermes capability lock: ${error.message}`)
  }
  if (lock?.version !== 1 || !Array.isArray(lock?.mcp_servers)) {
    throw new Error('Invalid Hermes capability lock schema')
  }
  const record = lock.mcp_servers.find(entry => entry?.id === 'omniroute')
  if (!record) throw new Error('OmniRoute is not approved by the Hermes capability lock')
  if (record.version !== packageVersion) {
    throw new Error(`OmniRoute capability version mismatch; expected ${record.version}, received ${packageVersion}`)
  }
  if (typeof record.server_sha256 !== 'string' || !record.server_sha256) {
    throw new Error('OmniRoute capability lock has no server.js hash')
  }
  const actual = await sha256File(serverPath)
  if (actual !== record.server_sha256) {
    throw new Error('OmniRoute server.js hash mismatch; run hermes capabilities update after review')
  }
}

function normalizePathForComparison(value) {
  const resolved = path.resolve(value)
  return process.platform === 'win32' ? resolved.toLowerCase() : resolved
}

function semverTuple(value) {
  const match = String(value || '').match(/^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$/)
  return match ? match.slice(1).map(Number) : null
}

function isSupportedVersion(value) {
  const current = semverTuple(value)
  const minimum = semverTuple(MINIMUM_OMNIROUTE_VERSION)
  if (!current || !minimum || current[0] !== MAXIMUM_OMNIROUTE_MAJOR) return false
  for (let index = 0; index < 3; index += 1) {
    if (current[index] > minimum[index]) return true
    if (current[index] < minimum[index]) return false
  }
  return true
}

export function defaultTrustedOmniRouteRoots() {
  const home = os.homedir()
  const roots = []

  if (process.platform === 'win32') {
    roots.push(path.join(home, 'AppData', 'Roaming', 'npm', 'node_modules', 'omniroute'))
    roots.push(path.join(path.dirname(process.execPath), 'node_modules', 'omniroute'))
  } else {
    roots.push('/usr/local/lib/node_modules/omniroute')
    roots.push('/usr/lib/node_modules/omniroute')
    roots.push(path.join(home, '.npm-global', 'lib', 'node_modules', 'omniroute'))
  }

  return roots
}

export async function resolveTrustedOmniRouteRoot({
  requestedRoot,
  allowedRoots = defaultTrustedOmniRouteRoots(),
  capabilitiesLockPath
} = {}) {
  const existingAllowedRoots = []
  for (const candidate of allowedRoots) {
    try {
      existingAllowedRoots.push(await fs.promises.realpath(candidate))
    } catch {
      // Missing known install locations are expected.
    }
  }

  let selected
  if (requestedRoot) {
    let canonicalRequested
    try {
      canonicalRequested = await fs.promises.realpath(requestedRoot)
    } catch (error) {
      throw new Error(`Requested OmniRoute package root is unavailable: ${error.message}`)
    }
    const requestedKey = normalizePathForComparison(canonicalRequested)
    selected = existingAllowedRoots.find(root => normalizePathForComparison(root) === requestedKey)
    if (!selected) {
      throw new Error('Requested OmniRoute package root is not in the trusted install roots')
    }
  } else {
    selected = existingAllowedRoots[0]
  }

  if (!selected) {
    throw new Error('OmniRoute package root not found in a trusted install location')
  }

  const packageJsonPath = path.join(selected, 'package.json')
  const serverPath = path.join(selected, 'dist', 'open-sse', 'mcp-server', 'server.js')
  let packageJson
  try {
    packageJson = JSON.parse(await fs.promises.readFile(packageJsonPath, 'utf8'))
  } catch (error) {
    throw new Error(`Invalid OmniRoute package metadata: ${error.message}`)
  }

  if (packageJson.name !== 'omniroute') {
    throw new Error(`Unexpected package identity '${String(packageJson.name || '')}'; expected 'omniroute'`)
  }
  if (!isSupportedVersion(packageJson.version)) {
    throw new Error(
      `Unsupported OmniRoute version '${String(packageJson.version || '')}'; expected >=${MINIMUM_OMNIROUTE_VERSION} <4.0.0`
    )
  }

  let canonicalServer
  try {
    canonicalServer = await fs.promises.realpath(serverPath)
  } catch (error) {
    throw new Error(`Compiled OmniRoute MCP server is unavailable: ${error.message}`)
  }
  const relative = path.relative(selected, canonicalServer)
  if (relative.startsWith('..') || path.isAbsolute(relative)) {
    throw new Error('Compiled OmniRoute MCP server escapes the trusted package root')
  }

  await verifyLockedOmniRouteServer(canonicalServer, packageJson.version, capabilitiesLockPath)

  return selected
}
