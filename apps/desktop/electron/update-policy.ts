'use strict'

/**
 * update-policy.ts
 *
 * Decide se um auto-update pode prosseguir para uma instalação — PURO, testável
 * sem Electron. Causa raiz do boot-loop P0: o desktop auto-atualizava um FORK
 * (branch `feature/…`, 370 atrás de `main`) cegamente para `main`, matando o
 * backend a cada boot e arriscando sobrescrever o trabalho do fork.
 *
 * Regra: auto-update automático SÓ para um checkout oficial, limpo, no branch
 * que o desktop rastreia. Qualquer sinal de fork / divergência / trabalho local
 * → MANUAL_REQUIRED (o backend inicia normal; o update vira notificação, nunca
 * mutação destrutiva). Nunca sobrescrever fork/trabalho local.
 */

export enum UpdatePolicy {
  AUTO = 'auto', // checkout oficial limpo no branch de update → pode auto-atualizar
  MANUAL_REQUIRED = 'manual_required', // fork/divergente/sujo/dev → só notifica
  UP_TO_DATE = 'up_to_date' // nada a fazer
}

export interface InstallState {
  /** Branch atual do checkout (ex.: 'feature/hermes-omniroute-studio'). */
  currentBranch: string
  /** Branch que o desktop rastreia para update (ex.: 'main'). */
  updateBranch: string
  /** Commits atrás do alvo. null = "update disponível, contagem desconhecida". */
  behind: number | null
  /** Commits locais À FRENTE do alvo de update (trabalho local). */
  ahead: number
  /** Working tree com mudanças não commitadas. */
  dirty: boolean
  /** origin é o upstream oficial do Hermes (não um fork). */
  remoteIsOfficialUpstream: boolean
}

export interface UpdateDecision {
  policy: UpdatePolicy
  autoUpdateAllowed: boolean
  /** Motivos legíveis para MANUAL_REQUIRED — vão para o log e a UX. Sem secrets. */
  reasons: string[]
}

/**
 * Núcleo do fork-guard. Ordem: primeiro os sinais de "não é uma instalação
 * oficial limpa" (que bloqueiam o auto-update em qualquer contagem), depois
 * up-to-date, depois AUTO.
 */
export function resolveUpdatePolicy(state: InstallState): UpdateDecision {
  const reasons: string[] = []

  const currentBranch = (state.currentBranch || '').trim()
  const updateBranch = (state.updateBranch || '').trim()

  // Unknown != safe. If we could not determine the current branch (git read
  // failed → empty) or the tracked update branch, we CANNOT confirm this is the
  // official tracked branch, so we must NOT auto-update — a failed read must
  // never be silently treated as "on the tracked branch, not divergent".
  if (!currentBranch || !updateBranch) {
    reasons.push('não foi possível determinar o branch atual/rastreado do checkout (estado desconhecido → manual)')
  }
  if (currentBranch && updateBranch && currentBranch !== updateBranch) {
    reasons.push(`checkout está no branch '${currentBranch}', mas o update rastreia '${updateBranch}'`)
  }
  if (state.dirty) {
    reasons.push('a working tree tem mudanças não commitadas')
  }
  if (Number.isFinite(state.ahead) && state.ahead > 0) {
    reasons.push(`${state.ahead} commit(s) local(is) à frente do alvo de update`)
  }
  if (!state.remoteIsOfficialUpstream) {
    reasons.push('a origin não é o upstream oficial do Hermes')
  }

  if (reasons.length > 0) {
    // Fork / divergência / trabalho local: NUNCA auto-atualizar (protege o fork).
    return { policy: UpdatePolicy.MANUAL_REQUIRED, autoUpdateAllowed: false, reasons }
  }

  if (state.behind === 0) {
    return { policy: UpdatePolicy.UP_TO_DATE, autoUpdateAllowed: false, reasons: [] }
  }

  // Checkout oficial, limpo, no branch de update, e atrás (ou contagem
  // desconhecida = disponível): auto-update seguro.
  return { policy: UpdatePolicy.AUTO, autoUpdateAllowed: true, reasons: [] }
}

/**
 * Reconhece se um remote é o upstream oficial do Hermes. Conservador: só
 * `NousResearch/hermes-agent` (http/https/ssh, com/sem .git) conta como oficial;
 * qualquer outro dono (um fork) → false. Um remote vazio/desconhecido → false
 * (falha fechada: trata como fork, não auto-atualiza).
 */
export function isOfficialUpstream(originUrl: string): boolean {
  const url = (originUrl || '').trim().toLowerCase()
  if (!url) {
    return false
  }
  // normaliza git@github.com:Owner/repo.git e https://github.com/Owner/repo(.git)
  const m = url.match(/github\.com[:/]+([^/]+)\/([^/]+?)(?:\.git)?\/?$/)
  if (!m) {
    return false
  }
  const [, owner, repo] = m
  return owner === 'nousresearch' && repo === 'hermes-agent'
}
