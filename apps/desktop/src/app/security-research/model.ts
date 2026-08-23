/**
 * View-model do Security Research — máquina de estados + gate de capacidade.
 *
 * Puro (sem React/IPC): decide o que é permitido e como o estado transiciona,
 * de forma testável sem app rodando. A defesa está aqui, no ponto de decisão:
 *   - só modos PLANOS rodam pela UI; modo exec-untrusted → BLOCKED (sandbox
 *     real é Linux; no Windows nativo não há contenção);
 *   - startRun exige a capacidade do modo concedida (mínimo privilégio);
 *   - transições de status são allowlisted (cancel-race não corrompe estado);
 *   - eventos de run duplicados são idempotentes (dedup por status+progress).
 */

import {
  Capability,
  type Capabilities,
  FLAT_MODES,
  MODE_CAPABILITY,
  RunStatus,
  type SecurityError,
  SecurityMode
} from './types'

export enum StartDecision {
  ALLOW = 'allow',
  BLOCKED_PLATFORM = 'blocked_platform', // modo exec-untrusted sem sandbox
  DENIED_CAPABILITY = 'denied_capability',
  DENIED_UNKNOWN_MODE = 'denied_unknown_mode',
  BUSY = 'busy' // já há um run ativo
}

const ACTIVE_STATUSES: ReadonlySet<RunStatus> = new Set([
  RunStatus.PREFLIGHT,
  RunStatus.RUNNING,
  RunStatus.CANCELLING
])

// Transições de status permitidas. Fora disto = ignorado (não corrompe).
const ALLOWED_TRANSITIONS: Readonly<Record<RunStatus, ReadonlySet<RunStatus>>> = {
  [RunStatus.IDLE]: new Set([RunStatus.PREFLIGHT, RunStatus.BLOCKED]),
  [RunStatus.PREFLIGHT]: new Set([RunStatus.READY, RunStatus.BLOCKED, RunStatus.FAILED]),
  [RunStatus.READY]: new Set([RunStatus.RUNNING, RunStatus.IDLE]),
  [RunStatus.RUNNING]: new Set([RunStatus.CANCELLING, RunStatus.COMPLETED, RunStatus.FAILED]),
  [RunStatus.CANCELLING]: new Set([RunStatus.COMPLETED, RunStatus.FAILED]),
  [RunStatus.COMPLETED]: new Set([RunStatus.IDLE, RunStatus.PREFLIGHT]),
  [RunStatus.FAILED]: new Set([RunStatus.IDLE, RunStatus.PREFLIGHT]),
  [RunStatus.BLOCKED]: new Set([RunStatus.IDLE, RunStatus.PREFLIGHT])
}

export function canTransition(from: RunStatus, to: RunStatus): boolean {
  if (from === to) {
    return true // idempotente (evento de run reentregue)
  }
  return ALLOWED_TRANSITIONS[from]?.has(to) ?? false
}

export function isFlatMode(mode: string): mode is SecurityMode {
  return (FLAT_MODES as readonly string[]).includes(mode)
}

/** Decide se um run pode começar — modo plano + capacidade + não ocupado. */
export function decideStart(params: {
  mode: string
  capabilities: Capabilities
  currentStatus: RunStatus
}): StartDecision {
  const { mode, capabilities, currentStatus } = params
  if (ACTIVE_STATUSES.has(currentStatus)) {
    return StartDecision.BUSY
  }
  if (!isFlatMode(mode)) {
    // modo exec-untrusted (fuzz/binary/exploit/…) ou desconhecido
    return StartDecision.BLOCKED_PLATFORM
  }
  if (!capabilities.modes.includes(mode)) {
    return StartDecision.DENIED_UNKNOWN_MODE
  }
  const required: Capability = MODE_CAPABILITY[mode]
  if (!capabilities.granted.includes(required)) {
    return StartDecision.DENIED_CAPABILITY
  }
  return StartDecision.ALLOW
}

export interface RunView {
  status: RunStatus
  progress: number
  error?: SecurityError
}

export const INITIAL_RUN_VIEW: RunView = { status: RunStatus.IDLE, progress: 0 }

export interface RunEvent {
  status: RunStatus
  progress?: number
  error?: SecurityError
}

/** Aplica um evento de run ao estado. Transição inválida → estado inalterado
 *  (cancel-race, evento fora de ordem). Duplicado → idempotente. Progresso só
 *  avança (nunca retrocede por reentrega). */
export function applyRunEvent(view: RunView, event: RunEvent): RunView {
  if (!canTransition(view.status, event.status)) {
    return view
  }
  const nextProgress = clampProgress(event.progress, view.progress, event.status)
  const next: RunView = { status: event.status, progress: nextProgress }
  if (event.error) {
    next.error = event.error
  } else if (event.status !== RunStatus.FAILED && event.status !== RunStatus.BLOCKED) {
    // limpa erro ao sair de um estado de falha
    delete next.error
  } else {
    next.error = view.error
  }
  return next
}

function clampProgress(incoming: number | undefined, current: number, status: RunStatus): number {
  if (status === RunStatus.COMPLETED) {
    return 1
  }
  if (incoming === undefined || !Number.isFinite(incoming)) {
    return current
  }
  const bounded = Math.max(0, Math.min(1, incoming))
  // monotônico: reentrega/duplicado não faz a barra voltar
  return Math.max(current, bounded)
}
