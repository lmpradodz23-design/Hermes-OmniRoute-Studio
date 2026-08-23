/**
 * Saneamento de dados UNTRUSTED do RAPTOR (finding/report/status).
 *
 * Finding e report vêm do scanner/LLM/repositório analisado — dado hostil por
 * padrão. Antes de chegar à UI: enums validados (valor desconhecido → UNKNOWN,
 * nunca crash), texto limitado e sem control chars, contagem limitada, status
 * inválido rejeitado. Nada aqui interpreta o conteúdo como instrução.
 */

import {
  Confidence,
  type Finding,
  FindingState,
  MAX_FINDING_TEXT,
  MAX_FINDINGS,
  MAX_REPORT_BYTES,
  RunStatus,
  type SecurityReport,
  Severity
} from './types'

export class SecurityDataError extends Error {}

// eslint-disable-next-line no-control-regex -- stripping control chars is the point
const CONTROL_CHARS = /[\u0000-\u001F\u007F]/g

/** Limita e remove control chars. Preserva o texto como DADO (não executa). */
export function sanitizeText(value: unknown, max = MAX_FINDING_TEXT): string {
  const raw = typeof value === 'string' ? value : String(value ?? '')
  const stripped = raw.replace(CONTROL_CHARS, '')
  return stripped.length > max ? stripped.slice(0, max) : stripped
}

function asEnum<T extends Record<string, string>>(e: T, value: unknown, fallback: T[keyof T]): T[keyof T] {
  const v = typeof value === 'string' ? value : ''
  return (Object.values(e) as string[]).includes(v) ? (v as T[keyof T]) : fallback
}

function asLine(value: unknown): number {
  const n = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(n) || n < 0) {
    return 0
  }
  return Math.min(Math.floor(n), 2_000_000_000)
}

/** Normaliza um finding hostil num Finding seguro. Nunca lança por conteúdo. */
export function validateFinding(raw: unknown): Finding {
  if (typeof raw !== 'object' || raw === null) {
    throw new SecurityDataError('finding não é um objeto')
  }
  const r = raw as Record<string, unknown>
  const id = sanitizeText(r.id, 256)
  if (!id) {
    throw new SecurityDataError('finding sem id')
  }
  return {
    id,
    ruleId: sanitizeText(r.ruleId ?? r.rule_id, 256),
    title: sanitizeText(r.title, 512),
    severity: asEnum(Severity, r.severity, Severity.UNKNOWN),
    confidence: asEnum(Confidence, r.confidence, Confidence.UNKNOWN),
    state: asEnum(FindingState, r.state, FindingState.CANDIDATE),
    file: sanitizeText(r.file, 1024),
    line: asLine(r.line),
    message: sanitizeText(r.message),
    untrusted: true
  }
}

export function validateFindings(raw: unknown): Finding[] {
  if (!Array.isArray(raw)) {
    throw new SecurityDataError('findings não é uma lista')
  }
  const capped = raw.slice(0, MAX_FINDINGS)
  const out: Finding[] = []
  const seen = new Set<string>()
  for (const item of capped) {
    try {
      const f = validateFinding(item)
      if (!seen.has(f.id)) {
        seen.add(f.id)
        out.push(f)
      }
    } catch {
      // um finding hostil malformado é descartado, não derruba a lista inteira
    }
  }
  return out
}

export function validateReport(raw: unknown): SecurityReport {
  if (typeof raw !== 'object' || raw === null) {
    throw new SecurityDataError('report não é um objeto')
  }
  const r = raw as Record<string, unknown>
  const runId = sanitizeText(r.runId ?? r.run_id, 256)
  if (!runId) {
    throw new SecurityDataError('report sem runId')
  }
  const format = r.format === 'sarif' ? 'sarif' : 'markdown'
  const rawContent = typeof r.content === 'string' ? r.content : ''
  const bytes = Buffer.byteLength(rawContent, 'utf8')
  const truncated = bytes > MAX_REPORT_BYTES || r.truncated === true
  // corta por bytes (aprox. por chars quando estourar) para não estourar memória
  const content = bytes > MAX_REPORT_BYTES ? rawContent.slice(0, MAX_REPORT_BYTES) : rawContent
  return { runId, format, content, truncated }
}

/** Status vindo do transporte precisa ser um RunStatus conhecido. */
export function validateStatus(value: unknown): RunStatus {
  const v = typeof value === 'string' ? value : ''
  if (!(Object.values(RunStatus) as string[]).includes(v)) {
    throw new SecurityDataError(`status inválido do transporte: ${JSON.stringify(value)}`)
  }
  return v as RunStatus
}
