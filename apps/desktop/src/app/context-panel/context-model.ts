/**
 * Context panel unificado — lógica pura de quais abas mostrar e do readout de
 * contexto/segurança. NÃO cria um segundo right sidebar: o pane-tree já suporta
 * panes empilhados (tabs). Este módulo decide o conteúdo; a montagem no tree e a
 * aparência final ficam para validação visual no executor Windows.
 *
 * Regra: aba sem conteúdo real não aparece (nada de tab vazia/placeholder).
 */

export enum ContextTab {
  FILES = 'files',
  ARTIFACTS = 'artifacts',
  CHANGES = 'changes',
  PREVIEW = 'preview',
  CONTEXT = 'context',
  TOOLS = 'tools'
}

// Ordem canônica de exibição.
const TAB_ORDER: readonly ContextTab[] = [
  ContextTab.FILES,
  ContextTab.ARTIFACTS,
  ContextTab.CHANGES,
  ContextTab.PREVIEW,
  ContextTab.CONTEXT,
  ContextTab.TOOLS
]

export interface PanelContent {
  hasFiles: boolean
  artifactCount: number
  changedFileCount: number
  hasPreview: boolean
  /** Context é sempre útil quando há um projeto ativo. */
  hasProject: boolean
  activeToolCount: number
}

/** Abas visíveis dado o conteúdo real. Vazio → sem painel. */
export function visibleTabs(content: PanelContent): ContextTab[] {
  const present: Record<ContextTab, boolean> = {
    [ContextTab.FILES]: content.hasFiles,
    [ContextTab.ARTIFACTS]: content.artifactCount > 0,
    [ContextTab.CHANGES]: content.changedFileCount > 0,
    [ContextTab.PREVIEW]: content.hasPreview,
    [ContextTab.CONTEXT]: content.hasProject,
    [ContextTab.TOOLS]: content.activeToolCount > 0
  }
  return TAB_ORDER.filter(tab => present[tab])
}

/** A aba ativa deve continuar válida quando o conteúdo muda (session/project
 *  switch). Se sumiu, cai para a primeira visível; se nada visível, null. */
export function resolveActiveTab(previous: ContextTab | null, visible: ContextTab[]): ContextTab | null {
  if (previous && visible.includes(previous)) {
    return previous
  }
  return visible[0] ?? null
}

// ── Context / security readout ──────────────────────────────────────────────

export enum ContextSecurity {
  LOCAL_ONLY = 'local_only',
  REDACTED = 'redacted', // redact-before-cloud ativo
  CLOUD_ALLOWED = 'cloud_allowed'
}

export interface SecurityConfigView {
  localOnly: boolean
  redactBeforeCloud: boolean
}

/** Tri-state derivado da MESMA config que o backend enforça (não é enforcement,
 *  é reflexo). local-only vence redact vence cloud. */
export function deriveContextSecurity(cfg: SecurityConfigView): ContextSecurity {
  if (cfg.localOnly) {
    return ContextSecurity.LOCAL_ONLY
  }
  if (cfg.redactBeforeCloud) {
    return ContextSecurity.REDACTED
  }
  return ContextSecurity.CLOUD_ALLOWED
}

export interface ContextSnapshot {
  project: string
  cwd: string
  fileCount: number
  memoryEnabled: boolean
  goalTitle: string | null
  model: string
  security: ContextSecurity
}

/** Monta o readout compacto do contexto ativo a partir do estado real. Campos
 *  ausentes ficam vazios/zero — nunca inventados. */
export function deriveContextSnapshot(input: {
  project?: string
  cwd?: string
  fileCount?: number
  memoryEnabled?: boolean
  goalTitle?: string | null
  model?: string
  security: SecurityConfigView
}): ContextSnapshot {
  return {
    project: input.project ?? '',
    cwd: input.cwd ?? '',
    fileCount: Math.max(0, Math.floor(input.fileCount ?? 0)),
    memoryEnabled: Boolean(input.memoryEnabled),
    goalTitle: input.goalTitle ?? null,
    model: input.model ?? '',
    security: deriveContextSecurity(input.security)
  }
}
