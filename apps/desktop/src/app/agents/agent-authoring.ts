/**
 * Autoria de agentes no U1 — camada de domínio desacoplada. Reusa a infra de
 * agentes/subagentes existente (store/subagents.ts fornece a VISUALIZAÇÃO); aqui
 * ficam as AÇÕES (select/create/edit/delegate/cancel) e o gate. A execução real
 * (criar/delegar) aciona o runtime de subagentes via gateway — device-blocked.
 */

export enum AgentActionKind {
  SELECT = 'select',
  VIEW = 'view',
  CREATE = 'create',
  EDIT = 'edit',
  DELEGATE = 'delegate',
  CANCEL = 'cancel'
}

// Ações que só leem (sem gateway) vs. as que mutam (exigem gateway + permissão).
const READ_ONLY_ACTIONS: ReadonlySet<AgentActionKind> = new Set([AgentActionKind.SELECT, AgentActionKind.VIEW])

export enum AgentActionDecision {
  ALLOW = 'allow',
  BLOCKED_GATEWAY = 'blocked_gateway',
  DENIED_CAPABILITY = 'denied_capability',
  INVALID = 'invalid'
}

export const MAX_AGENT_NAME = 120
export const MAX_AGENT_INSTRUCTIONS = 20_000

export interface AgentDraft {
  name: string
  instructions: string
  tools: string[]
}

export interface AgentDraftError {
  field: 'name' | 'instructions'
  message: string
}

/** Valida um rascunho de agente. Retorna erros de campo; não lança. */
export function validateAgentDraft(draft: AgentDraft): AgentDraftError[] {
  const errors: AgentDraftError[] = []
  const name = (draft.name || '').trim()
  if (!name) {
    errors.push({ field: 'name', message: 'nome obrigatório' })
  } else if (name.length > MAX_AGENT_NAME) {
    errors.push({ field: 'name', message: `nome acima de ${MAX_AGENT_NAME}` })
  }
  if ((draft.instructions || '').length > MAX_AGENT_INSTRUCTIONS) {
    errors.push({ field: 'instructions', message: 'instruções muito longas' })
  }
  return errors
}

export interface AgentActionContext {
  hasGateway: boolean
  capabilityGranted: boolean
  draft?: AgentDraft
}

/** Decide se uma ação de autoria pode prosseguir. Ações que mutam exigem
 *  gateway vivo + permissão; sem isso a UI mostra o motivo real (não um botão
 *  que finge funcionar). */
export function decideAgentAction(action: AgentActionKind, ctx: AgentActionContext): AgentActionDecision {
  if (READ_ONLY_ACTIONS.has(action)) {
    return AgentActionDecision.ALLOW
  }
  if ((action === AgentActionKind.CREATE || action === AgentActionKind.EDIT) && ctx.draft) {
    if (validateAgentDraft(ctx.draft).length > 0) {
      return AgentActionDecision.INVALID
    }
  }
  if (!ctx.capabilityGranted) {
    return AgentActionDecision.DENIED_CAPABILITY
  }
  if (!ctx.hasGateway) {
    return AgentActionDecision.BLOCKED_GATEWAY
  }
  return AgentActionDecision.ALLOW
}

export interface AgentRef {
  id: string
  name: string
}

export interface AgentTransport {
  listAgents(): Promise<AgentRef[]>
  createAgent(draft: AgentDraft): Promise<AgentRef>
  editAgent(id: string, draft: AgentDraft): Promise<AgentRef>
  delegate(id: string, task: string): Promise<{ runId: string }>
  cancel(runId: string): Promise<void>
}
