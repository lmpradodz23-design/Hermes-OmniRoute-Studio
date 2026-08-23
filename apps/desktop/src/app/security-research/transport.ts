/**
 * Fronteira única entre a UI de Security Research e o backend RAPTOR.
 *
 * A implementação real faz IPC ao gateway (device-blocked neste ambiente). A UI
 * e o view-model dependem SÓ desta interface — trocar transporte (real, fake de
 * teste, futuro remoto) não toca a UI. Um transporte fake existe SOMENTE em
 * teste e NUNCA pode ser usado para declarar RAPTOR_REAL_IPC=PASS.
 */

import type {
  Capabilities,
  Finding,
  Health,
  SecurityMode,
  SecurityReport,
  SecurityRun
} from './types'

export interface StartRunInput {
  mode: SecurityMode
  /** Caminho do alvo autorizado (resolvido/validado no backend). */
  targetPath: string
}

export interface SecurityResearchTransport {
  getHealth(): Promise<Health>
  getCapabilities(): Promise<Capabilities>
  startRun(input: StartRunInput): Promise<SecurityRun>
  getRun(runId: string): Promise<SecurityRun>
  cancelRun(runId: string): Promise<SecurityRun>
  listFindings(runId: string): Promise<Finding[]>
  getFinding(runId: string, findingId: string): Promise<Finding>
  getReport(runId: string, format: 'sarif' | 'markdown'): Promise<SecurityReport>
}
