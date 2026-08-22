import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

export type GuardrailTaintStatus = {
  active: boolean
  at: string | null
  detail: string | null
  source: 'external-file' | 'installed-skill' | 'mcp-external' | 'memory' | 'web' | null
  turnsAgo: number | null
}

const INACTIVE: GuardrailTaintStatus = {
  active: false,
  at: null,
  detail: null,
  source: null,
  turnsAgo: null
}

const SOURCES = new Set(['external-file', 'installed-skill', 'mcp-external', 'memory', 'web'])

export function readGuardrailTaintStatus(hermesHome: string, rawSessionId: unknown): GuardrailTaintStatus {
  if (typeof rawSessionId !== 'string' || rawSessionId.length === 0 || rawSessionId.length > 256) {
    return INACTIVE
  }

  const digest = crypto.createHash('sha256').update(rawSessionId, 'utf8').digest('hex')
  const statusPath = path.join(hermesHome, 'runtime', 'guardrail-taint', `${digest}.json`)

  try {
    const stat = fs.statSync(statusPath)

    if (!stat.isFile() || stat.size > 8_192) {
      return INACTIVE
    }

    const value = JSON.parse(fs.readFileSync(statusPath, 'utf8')) as Record<string, unknown>
    const source = typeof value.source === 'string' && SOURCES.has(value.source) ? value.source : null

    const turnsAgo =
      typeof value.turns_ago === 'number' && Number.isInteger(value.turns_ago) && value.turns_ago >= 0
        ? Math.min(value.turns_ago, 100)
        : null

    if (value.active !== true || source === null || turnsAgo === null) {
      return INACTIVE
    }

    return {
      active: true,
      at: typeof value.at === 'string' ? value.at.slice(0, 64) : null,
      detail: typeof value.detail === 'string' ? value.detail.slice(0, 240) : null,
      source: source as GuardrailTaintStatus['source'],
      turnsAgo
    }
  } catch {
    return INACTIVE
  }
}
