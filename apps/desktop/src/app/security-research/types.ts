/**
 * Security Research (RAPTOR) — modelos do domínio da UI, espelhando o backend
 * real (`security_research/` no Python). A UI NUNCA conhece a implementação
 * interna do RAPTOR; fala só com estes tipos + o SecurityResearchTransport.
 *
 * Espelha, sem inventar: RaptorMode, Severity/Confidence/FindingState e
 * Capability do backend. Modos que executam conteúdo não confiável exigem
 * sandbox real (Linux) — no Windows nativo eles são BLOCKED_BY_PLATFORM, nunca
 * fake progress.
 */

// Modos planos: rodam controlados, sem executar conteúdo não confiável.
export enum SecurityMode {
  DESCRIBE = 'describe', // preflight read-only
  SCAN = 'scan', // scanner estático (semgrep)
  SCA = 'sca', // supply-chain
  ANALYZE = 'analyze' // consome SARIF
}

// Modos que executam conteúdo não confiável — exigem sandbox comprovado.
export enum ExecUntrustedMode {
  FUZZ = 'fuzz',
  BINARY = 'binary',
  EXPLOIT = 'exploit',
  CRASH = 'crash-analysis',
  FRIDA = 'frida'
}

export const FLAT_MODES: readonly SecurityMode[] = Object.freeze([
  SecurityMode.DESCRIBE,
  SecurityMode.SCAN,
  SecurityMode.SCA,
  SecurityMode.ANALYZE
])

export const EXEC_UNTRUSTED_MODES: readonly string[] = Object.freeze(Object.values(ExecUntrustedMode))

// Capacidade (mínimo privilégio) — espelha security_research/permissions.py.
export enum Capability {
  READ_PROJECT = 'read_project',
  EXECUTE_SCANNER = 'execute_scanner',
  NETWORK_LOOKUP = 'network_lookup',
  EXECUTE_BINARY = 'execute_binary',
  FUZZ = 'fuzz',
  GENERATE_POC = 'generate_poc',
  APPLY_PATCH = 'apply_patch',
  SHELL = 'shell',
  SSH = 'ssh',
  CRON = 'cron'
}

// Capacidade mínima que cada modo plano exige (espelha _MODE_CAPABILITY).
export const MODE_CAPABILITY: Readonly<Record<SecurityMode, Capability>> = Object.freeze({
  [SecurityMode.DESCRIBE]: Capability.READ_PROJECT,
  [SecurityMode.SCAN]: Capability.EXECUTE_SCANNER,
  [SecurityMode.SCA]: Capability.EXECUTE_SCANNER,
  [SecurityMode.ANALYZE]: Capability.READ_PROJECT
})

// Estado de uma execução (run) na UI.
export enum RunStatus {
  IDLE = 'idle',
  PREFLIGHT = 'preflight',
  READY = 'ready',
  RUNNING = 'running',
  CANCELLING = 'cancelling',
  COMPLETED = 'completed',
  FAILED = 'failed',
  BLOCKED = 'blocked' // ex.: modo exec-untrusted sem sandbox real
}

export enum Severity {
  CRITICAL = 'critical',
  HIGH = 'high',
  MEDIUM = 'medium',
  LOW = 'low',
  INFO = 'info',
  UNKNOWN = 'unknown'
}

export enum Confidence {
  HIGH = 'high',
  MEDIUM = 'medium',
  LOW = 'low',
  UNKNOWN = 'unknown'
}

export enum FindingState {
  CANDIDATE = 'candidate',
  VALIDATING = 'validating',
  CONFIRMED = 'confirmed',
  FALSE_POSITIVE = 'false_positive',
  DISPUTED = 'disputed',
  FIXING = 'fixing',
  FIXED = 'fixed',
  REGRESSION_FAILED = 'regression_failed',
  BLOCKED = 'blocked'
}

/** UNTRUSTED_DATA — vem do scanner/LLM/repositório analisado. Nunca é comando. */
export interface Finding {
  id: string
  ruleId: string
  title: string
  severity: Severity
  confidence: Confidence
  state: FindingState
  file: string
  line: number
  message: string
  untrusted: true
}

export interface SecurityRun {
  id: string
  mode: SecurityMode
  status: RunStatus
  progress: number // 0..1
  startedAt: number
  finishedAt?: number
  error?: SecurityError
  findingCount: number
}

export interface SecurityReport {
  runId: string
  format: 'sarif' | 'markdown'
  /** Conteúdo já validado/limitado; UNTRUSTED. Vira artifact no fluxo existente. */
  content: string
  truncated: boolean
}

export interface SecurityError {
  code: 'unavailable' | 'platform_blocked' | 'denied' | 'invalid' | 'timeout' | 'transport' | 'cancelled'
  message: string
}

export interface Health {
  available: boolean
  raptorVersion?: string
  sandbox: 'none' | 'wsl2' | 'container' | 'seatbelt'
  canIsolateUntrustedExec: boolean
}

export interface Capabilities {
  modes: SecurityMode[]
  granted: Capability[]
}

// Teto defensivo do conteúdo de report/finding vindo do backend (UNTRUSTED).
export const MAX_REPORT_BYTES = 8 * 1024 * 1024 // 8MB
export const MAX_FINDING_TEXT = 4096
export const MAX_FINDINGS = 10_000
