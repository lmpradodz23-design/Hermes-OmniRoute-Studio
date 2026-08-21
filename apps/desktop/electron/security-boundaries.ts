import fs from 'node:fs'
import path from 'node:path'

import { sensitiveFileBlockReason } from './hardening'

export const DEFAULT_OMNIROUTE_MCP_SCOPES = [
  'execute:completions',
  'read:combos',
  'read:health',
  'read:models',
  'read:quota',
  'read:usage'
] as const

const EXECUTABLE_FILE_EXTENSIONS = new Set([
  '.bat',
  '.cmd',
  '.com',
  '.exe',
  '.jar',
  '.js',
  '.lnk',
  '.msi',
  '.ps1',
  '.scr',
  '.vbs'
])

function comparisonKey(value: string): string {
  const resolved = path.resolve(value)

  return process.platform === 'win32' ? resolved.toLowerCase() : resolved
}

function canonicalExistingAncestor(value: string): string {
  let cursor = path.resolve(value)
  const tail: string[] = []

  while (!fs.existsSync(cursor)) {
    const parent = path.dirname(cursor)

    if (parent === cursor) {break}
    tail.unshift(path.basename(cursor))
    cursor = parent
  }

  const canonical = fs.realpathSync.native(cursor)

  return path.resolve(canonical, ...tail)
}

export function resolveAllowedFsIpcPath(value: string, allowedRoots: readonly string[]): string {
  const resolved = canonicalExistingAncestor(value)
  const targetKey = comparisonKey(resolved)

  const allowed = allowedRoots.some(root => {
    if (!root) {return false}
    let canonicalRoot

    try {
      canonicalRoot = canonicalExistingAncestor(root)
    } catch {
      return false
    }

    const rootKey = comparisonKey(canonicalRoot)
    const relative = path.relative(rootKey, targetKey)

    return relative === '' || (!relative.startsWith('..') && !path.isAbsolute(relative))
  })

  if (!allowed) {
    throw new Error('Filesystem operation blocked: path is outside the allowed roots')
  }

  return resolved
}

export function externalFileBlockReason(filePath: string): string | null {
  if (sensitiveFileBlockReason(filePath)) {
    return 'Sensitive files cannot be opened through an external application.'
  }

  if (EXECUTABLE_FILE_EXTENSIONS.has(path.extname(filePath).toLowerCase())) {
    return 'Executable files cannot be opened through an external application.'
  }

  return null
}
