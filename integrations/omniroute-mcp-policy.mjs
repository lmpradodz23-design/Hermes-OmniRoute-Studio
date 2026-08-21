import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

export const MINIMUM_OMNIROUTE_VERSION = '3.8.49'
export const MAXIMUM_OMNIROUTE_MAJOR = 3

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
  allowedRoots = defaultTrustedOmniRouteRoots()
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

  return selected
}
