/**
 * Model routing (OmniRoute) — modelo normalizado + derivação de rótulo, puro.
 *
 * OmniRoute decide provider/model/fallback no backend. A UI só REFLETE essa
 * decisão — nunca inventa provider nem duplica enforcement. `local_only` já é
 * enforçado em agent/local_only.py (PASS/canariado); aqui a UI apenas mostra o
 * estado coerente: em local-only, um provider de cloud NUNCA aparece como
 * executável — aparece como bloqueado.
 *
 * Onde a decisão real vem do gateway (device-blocked), este módulo define o
 * contrato + a derivação testável; o mapeamento do campo real fica pro executor.
 */

export enum RoutingMode {
  AUTO = 'auto',
  MANUAL = 'manual'
}

export enum RoutingStatusKind {
  RESOLVED = 'resolved',
  FALLBACK = 'fallback',
  BLOCKED_LOCAL_ONLY = 'blocked_local_only', // cloud pedido sob local-only
  PENDING = 'pending',
  UNAVAILABLE = 'unavailable'
}

// Espelha _LOCAL_PROVIDERS de agent/local_only.py.
const LOCAL_PROVIDERS: ReadonlySet<string> = new Set(['ollama', 'lmstudio', 'lm-studio', 'llama.cpp', 'llamacpp'])

export function isLocalProvider(provider: string, baseUrl = ''): boolean {
  const p = (provider || '').trim().toLowerCase()
  if (LOCAL_PROVIDERS.has(p)) {
    return true
  }
  const url = (baseUrl || '').trim().toLowerCase()
  return /(^|\/\/)(localhost|127\.0\.0\.1|\[::1\])(:|\/|$)/.test(url)
}

/** Estado de roteamento normalizado — o que o runtime fornece (ou fornecerá). */
export interface RoutingStatus {
  requestedMode: RoutingMode
  requestedModel: string // ex.: "auto/coding" ou um id explícito
  selectedProvider: string
  selectedModel: string
  selectionReason: string
  fallbackUsed: boolean
  localOnly: boolean
  kind: RoutingStatusKind
}

export interface RoutingLabel {
  /** Prefixo: "Auto", "Manual", "Fallback", "Local", "Bloqueado". */
  prefix: string
  /** Nome do modelo/provider selecionado, ou vazio quando indisponível. */
  target: string
  /** true quando NÃO deve ser apresentado como executável (ex.: cloud sob local-only). */
  blocked: boolean
}

/**
 * Deriva o rótulo a partir do estado REAL. Não inventa: se não há modelo
 * selecionado, o alvo fica vazio. Em local-only com provider de cloud, marca
 * blocked (a UI não pode oferecer cloud como executável).
 */
export function deriveRoutingLabel(status: RoutingStatus): RoutingLabel {
  const local = isLocalProvider(status.selectedProvider)

  if (status.kind === RoutingStatusKind.BLOCKED_LOCAL_ONLY || (status.localOnly && status.selectedProvider && !local)) {
    return { prefix: 'Bloqueado', target: status.selectedProvider || status.requestedModel, blocked: true }
  }
  if (status.kind === RoutingStatusKind.UNAVAILABLE) {
    return { prefix: 'Indisponível', target: '', blocked: true }
  }
  if (status.kind === RoutingStatusKind.PENDING || !status.selectedModel) {
    const prefix = status.requestedMode === RoutingMode.AUTO ? 'Auto' : 'Manual'
    return { prefix, target: '', blocked: false }
  }

  const target = local ? status.selectedModel : `${prettyProvider(status.selectedProvider)} ${status.selectedModel}`.trim()
  if (status.fallbackUsed || status.kind === RoutingStatusKind.FALLBACK) {
    return { prefix: 'Fallback', target, blocked: false }
  }
  if (local) {
    return { prefix: 'Local', target: status.selectedModel, blocked: false }
  }
  const prefix = status.requestedMode === RoutingMode.AUTO ? 'Auto' : 'Manual'
  return { prefix, target, blocked: false }
}

function prettyProvider(provider: string): string {
  const p = (provider || '').trim()
  const map: Record<string, string> = {
    anthropic: 'Claude',
    openai: 'OpenAI',
    google: 'Gemini',
    gemini: 'Gemini',
    mistral: 'Mistral',
    groq: 'Groq'
  }
  return map[p.toLowerCase()] ?? p
}

export interface RoutingStatusTransport {
  getRoutingStatus(sessionId: string): Promise<RoutingStatus>
}
