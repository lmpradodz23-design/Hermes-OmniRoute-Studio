/**
 * Superfície U1 do WhatsApp (OpenWA) — mapeia o estado REAL do provider para o
 * que a UI mostra. Reusa o contrato do backend (whatsapp_provider/session.py:
 * SessionState). NUNCA declara CONNECTED sem o estado real ser 'connected'; o QR
 * real continua sendo bloqueio humano (WAITING_FOR_HUMAN_QR_SCAN) só para
 * autenticação/E2E — não impede o resto do U1.
 */

// Estados de UI (o que o usuário vê).
export enum WhatsAppUiStatus {
  HEALTHY = 'healthy', // runtime up, ainda não conectado
  DISCONNECTED = 'disconnected',
  AUTH_REQUIRED = 'auth_required',
  QR_REQUIRED = 'qr_required',
  CONNECTED = 'connected',
  DEGRADED = 'degraded',
  FAILED = 'failed'
}

// Mapa 1:1 dos estados do backend (SessionState) para a UI. Estados sem conexão
// real NUNCA caem em CONNECTED.
const STATE_MAP: Readonly<Record<string, WhatsAppUiStatus>> = {
  disconnected: WhatsAppUiStatus.DISCONNECTED,
  starting: WhatsAppUiStatus.HEALTHY,
  qr_required: WhatsAppUiStatus.QR_REQUIRED,
  authenticating: WhatsAppUiStatus.AUTH_REQUIRED,
  connected: WhatsAppUiStatus.CONNECTED,
  degraded: WhatsAppUiStatus.DEGRADED,
  reconnecting: WhatsAppUiStatus.AUTH_REQUIRED,
  failed: WhatsAppUiStatus.FAILED,
  logged_out: WhatsAppUiStatus.AUTH_REQUIRED
}

/** Mapeia o estado do backend para a UI. Estado desconhecido → FAILED (falha
 *  fechada — jamais assume conexão). */
export function mapSessionState(backendState: string): WhatsAppUiStatus {
  const key = String(backendState || '').trim().toLowerCase()
  return STATE_MAP[key] ?? WhatsAppUiStatus.FAILED
}

/** Só é verdade quando o backend está realmente conectado. Guardrail contra
 *  "fingir conectado". */
export function canDeclareConnected(uiStatus: WhatsAppUiStatus): boolean {
  return uiStatus === WhatsAppUiStatus.CONNECTED
}

/** O envio/recebimento real só é permitido conectado ou degradado (espelha
 *  SessionStateMachine.can_send do backend). */
export function canSend(uiStatus: WhatsAppUiStatus): boolean {
  return uiStatus === WhatsAppUiStatus.CONNECTED || uiStatus === WhatsAppUiStatus.DEGRADED
}

/** Quando a UI deve mostrar o gate humano do QR. */
export function needsHumanQr(uiStatus: WhatsAppUiStatus): boolean {
  return uiStatus === WhatsAppUiStatus.QR_REQUIRED
}

export interface WhatsAppStatusView {
  status: WhatsAppUiStatus
  /** Rótulo do bloqueio quando aplicável. */
  blocker: 'WAITING_FOR_HUMAN_QR_SCAN' | null
}

export function deriveWhatsAppView(backendState: string): WhatsAppStatusView {
  const status = mapSessionState(backendState)
  return {
    status,
    blocker: needsHumanQr(status) ? 'WAITING_FOR_HUMAN_QR_SCAN' : null
  }
}

export interface WhatsAppSurfaceTransport {
  getStatus(sessionId: string): Promise<{ state: string }>
  runDiagnostics(sessionId: string): Promise<{ healthy: boolean; detail: string }>
}
