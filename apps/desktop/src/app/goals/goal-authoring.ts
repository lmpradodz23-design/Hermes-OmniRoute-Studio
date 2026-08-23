/**
 * "Transformar tarefa em Goal" — entrypoint desacoplado. Reusa o sistema de
 * goals existente (store/goals.ts, GoalStatus) — NÃO cria GoalV2.
 *
 * No Hermes o goal é definido pelo agente (que emite a linha "⊙ Goal set: …"),
 * e o store de goals é LIDO dessa saída. Então "criar goal a partir da tarefa" =
 * enviar ao agente uma instrução de set-goal derivada do texto da tarefa. Este
 * módulo produz essa instrução (puro/testável) e o contrato de acompanhamento.
 * A execução real (gateway/agente) é device-blocked.
 */

import type { GoalStatus } from '@/store/goals'

export const MAX_GOAL_TITLE = 200

export interface GoalDraft {
  title: string
  sourceSessionId: string
  sourceProject: string
}

/** Deriva um título de goal a partir do texto da tarefa (1ª linha significativa,
 *  limitada). Vazio se não há texto útil — nunca inventa um título. */
export function deriveGoalTitle(taskText: string): string {
  const firstLine = (taskText || '')
    .split('\n')
    .map(l => l.trim())
    .find(l => l.length > 0)
  if (!firstLine) {
    return ''
  }
  const clean = firstLine.replace(/\s+/g, ' ')
  return clean.length > MAX_GOAL_TITLE ? clean.slice(0, MAX_GOAL_TITLE) : clean
}

/** Instrução enviada ao agente para definir o goal. É o mesmo mecanismo que o
 *  agente já usa (⊙ Goal set) — não um caminho paralelo. */
export function buildGoalInstruction(draft: GoalDraft): string | null {
  const title = deriveGoalTitle(draft.title)
  if (!title) {
    return null
  }
  return `Set a goal for this task: ${title}`
}

// Transições de status de goal (espelha GoalStatus: active/waiting/paused/done).
const ALLOWED: Readonly<Record<GoalStatus, ReadonlySet<GoalStatus>>> = {
  active: new Set<GoalStatus>(['waiting', 'paused', 'done']),
  waiting: new Set<GoalStatus>(['active', 'paused', 'done']),
  paused: new Set<GoalStatus>(['active', 'waiting', 'done']),
  done: new Set<GoalStatus>([]) // terminal — done não volta sem novo goal
}

export function canGoalTransition(from: GoalStatus, to: GoalStatus): boolean {
  if (from === to) {
    return true
  }
  return ALLOWED[from]?.has(to) ?? false
}

export interface GoalRef {
  sessionId: string
  title: string
  status: GoalStatus
  progress: number
}

export interface GoalTransport {
  createGoal(draft: GoalDraft): Promise<GoalRef>
  getGoal(sessionId: string): Promise<GoalRef | null>
  cancelGoal(sessionId: string): Promise<GoalRef>
  resumeGoal(sessionId: string): Promise<GoalRef>
}
