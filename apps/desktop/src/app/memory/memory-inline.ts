/**
 * Affordance de memória inline no Workspace — mínima, sem replicar o Starmap
 * dentro do chat. Só decide QUAIS controles mostrar a partir do estado real.
 * "Forget" só aparece quando realmente suportado e há algo a esquecer; nunca
 * grava secrets (isso é enforçado na camada de memória do backend/whatsapp).
 */

export interface MemoryInlineState {
  enabled: boolean
  rememberedCount: number
  /** O provider de memória suporta remoção? (nem todos suportam.) */
  canForget: boolean
}

export interface MemoryAffordances {
  showEnabledIndicator: boolean
  showRememberedCount: boolean
  showOpenStarmap: boolean
  showForget: boolean
}

/** Deriva as affordances. Regras:
 *  - indicador de "enabled" só quando ligado;
 *  - contagem só quando ligado e há algo lembrado;
 *  - abrir Starmap sempre disponível (a superfície existe);
 *  - Forget só quando suportado E há algo a esquecer. */
export function memoryAffordances(state: MemoryInlineState): MemoryAffordances {
  const count = Math.max(0, Math.floor(state.rememberedCount || 0))
  return {
    showEnabledIndicator: state.enabled,
    showRememberedCount: state.enabled && count > 0,
    showOpenStarmap: true,
    showForget: state.enabled && state.canForget && count > 0
  }
}
