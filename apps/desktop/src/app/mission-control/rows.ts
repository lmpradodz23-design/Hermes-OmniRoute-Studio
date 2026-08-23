/**
 * Projeção de "o que está rodando", atravessando TODAS as sessões.
 *
 * ── Por que este arquivo existe ─────────────────────────────────────────────
 *
 * O Hermes já sabe tudo isto — só que espalhado em quatro superfícies, todas
 * presas ao contexto de UMA sessão ou a um overlay modal:
 *
 *   1. a status stack acima do composer  → só a sessão aberta;
 *   2. o overlay Agents                  → só subagentes, e cobre a tela;
 *   3. a statusbar                       → um contador, sem o "o quê";
 *   4. os dots na sidebar                → uma cor, sem o "por quê".
 *
 * Quem tem cinco sessões trabalhando ao mesmo tempo não consegue responder
 * "o que está rodando agora?" sem abrir cinco sessões, e um processo que
 * falhou numa sessão fechada não aparece em lugar nenhum além de um ponto
 * colorido. Esta projeção junta os mesmos dados numa lista só, ordenada por
 * urgência, e é o que o painel Mission Control renderiza.
 *
 * Aqui não há fetch, store nem React de propósito: entra estado, sai lista.
 * É o que torna a ordenação e o "o que conta como trabalho" testáveis sem
 * montar a UI inteira.
 */

import type { ClientSessionState } from '@/app/types'
import type { ComposerStatusItem, StatusItemType } from '@/store/composer-status'

/**
 * Todos ficam de fora: são o checklist do turno em andamento, não trabalho de
 * fundo. Incluí-los encheria o painel de linhas que somem sozinhas em segundos
 * e afogariam justamente o que ele existe para mostrar.
 */
const WORK_TYPES: readonly StatusItemType[] = ['goal', 'subagent', 'background']

export interface MissionGroup {
  failed: number
  items: readonly ComposerStatusItem[]
  running: number
  /** Id de runtime — é por ele que as ações (parar, dispensar) são endereçadas. */
  runtimeId: string
  /** Id armazenado, quando existe: é o que abre a sessão ao clicar. */
  storedId: null | string
  title: string
}

export interface MissionSummary {
  failed: number
  groups: readonly MissionGroup[]
  running: number
  sessions: number
}

const isWork = (item: ComposerStatusItem) => WORK_TYPES.includes(item.type)

/**
 * Ordem: quem falhou primeiro, depois quem está rodando, depois o resto.
 *
 * Falha vem antes de execução porque falha PARA de mudar sozinha — ela fica ali
 * até alguém olhar. Trabalho rodando ainda pode terminar bem sem intervenção
 * nenhuma. Um painel que ordena pelo mais barulhento (o que roda) enterra
 * exatamente a linha que precisa de uma pessoa.
 */
function compareGroups(a: MissionGroup, b: MissionGroup): number {
  if (a.failed !== b.failed) {
    return b.failed - a.failed
  }

  if (a.running !== b.running) {
    return b.running - a.running
  }

  return a.title.localeCompare(b.title)
}

export function buildMissionGroups(
  statusBySession: Readonly<Record<string, readonly ComposerStatusItem[]>>,
  sessionStates: Readonly<Record<string, ClientSessionState | undefined>>,
  titleFor: (storedId: null | string, runtimeId: string) => string
): MissionGroup[] {
  const groups: MissionGroup[] = []

  for (const [runtimeId, items] of Object.entries(statusBySession)) {
    const work = items.filter(isWork)

    if (work.length === 0) {
      continue
    }

    const storedId = sessionStates[runtimeId]?.storedSessionId ?? null

    groups.push({
      failed: work.filter(item => item.state === 'failed').length,
      items: work,
      running: work.filter(item => item.state === 'running').length,
      runtimeId,
      storedId,
      title: titleFor(storedId, runtimeId)
    })
  }

  return groups.sort(compareGroups)
}

export function summarize(groups: readonly MissionGroup[]): MissionSummary {
  return {
    failed: groups.reduce((total, group) => total + group.failed, 0),
    groups,
    running: groups.reduce((total, group) => total + group.running, 0),
    sessions: groups.length
  }
}

/**
 * Uma linha só pode ser parada quando é um processo de fundo em execução.
 *
 * Subagente e goal terminam pelo seu próprio ciclo — oferecer um botão "parar"
 * neles seria um botão que mente. Melhor não ter botão do que ter um que não
 * faz o que diz.
 */
export function canStop(item: ComposerStatusItem): boolean {
  return item.type === 'background' && item.state === 'running'
}

/** Linha encerrada pode sair da lista; linha viva, não. */
export function canDismiss(item: ComposerStatusItem): boolean {
  return item.type === 'background' && item.state !== 'running'
}
