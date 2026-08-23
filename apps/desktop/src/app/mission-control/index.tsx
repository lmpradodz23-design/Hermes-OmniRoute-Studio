/**
 * Mission Control — um painel que responde "o que está rodando agora?".
 *
 * Não é uma segunda implementação de nada: consome exatamente os mesmos stores
 * que a status stack do composer (`$statusItemsBySession`) e as mesmas ações
 * (`stopBackgroundProcess`, `dismissBackgroundProcess`, `refreshBackgroundProcesses`).
 * A diferença é o recorte — todas as sessões de uma vez, dentro da árvore de
 * panes, convivendo com o chat em vez de cobrir a tela como um overlay.
 *
 * A lógica de agrupar e ordenar mora em `rows.ts`, testada sem React.
 */

import { useStore } from '@nanostores/react'
import { useEffect, useMemo, useState } from 'react'

import { usePaneVisible } from '@/components/pane-shell/pane-visibility'
import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { Tip } from '@/components/ui/tooltip'
import { useI18n } from '@/i18n'
import type { Translations } from '@/i18n/types'
import { cn } from '@/lib/utils'
import {
  $statusItemsBySession,
  type ComposerStatusItem,
  dismissBackgroundProcess,
  refreshAllBackgroundProcesses,
  refreshBackgroundProcesses,
  stopBackgroundProcess
} from '@/store/composer-status'
import { notifyError } from '@/store/notifications'
import { $sessions } from '@/store/session'
import { $sessionStates } from '@/store/session-states'

import { SidebarPanelLabel } from '../shell/sidebar-label'

import { buildMissionGroups, canDismiss, canStop, type MissionGroup, summarize } from './rows'

// Rede de segurança: um processo que morre sem `notify_on_complete` não emite
// evento nenhum. O mesmo intervalo da status stack, e só enquanto há linha viva
// na tela — um painel aberto sobre nada não deve conversar com o gateway.
const POLL_MS = 5_000

const TYPE_ICON: Record<ComposerStatusItem['type'], string> = {
  background: 'server-process',
  goal: 'target',
  subagent: 'agent',
  todo: 'checklist'
}

const STATE_LABEL = (m: Translations['missionControl'], state: ComposerStatusItem['state']) =>
  state === 'failed' ? m.stateFailed : state === 'done' ? m.stateDone : m.stateRunning

const STATE_CLASS: Record<ComposerStatusItem['state'], string> = {
  done: 'text-(--ui-text-quaternary)',
  failed: 'text-(--dt-error, #f87171)',
  running: 'text-(--theme-primary)'
}

interface MissionControlPaneProps {
  onOpenSession?: (storedId: string) => void
}

export function MissionControlPane({ onOpenSession }: MissionControlPaneProps) {
  const { t } = useI18n()
  const m = t.missionControl
  const statusBySession = useStore($statusItemsBySession)
  const sessionStates = useStore($sessionStates)
  const sessions = useStore($sessions)

  const summary = useMemo(() => {
    const titleFor = (storedId: null | string, runtimeId: string) => {
      const found = sessions.find(session => session.id === storedId)

      if (found?.title?.trim()) {
        return found.title.trim()
      }

      // `$sessions` é só uma página de recentes: uma sessão antiga com processo
      // vivo cai aqui. Mostrar o UUID cru transforma o cabeçalho em ruído — a
      // convenção do resto do app é nomear pelo prefixo curto.
      const id = (storedId || runtimeId).trim()

      return id ? m.untitledSessionWithId(id.slice(0, 8)) : m.untitledSession
    }

    return summarize(buildMissionGroups(statusBySession, sessionStates, titleFor))
  }, [statusBySession, sessionStates, sessions, m.untitledSession])

  // Hidratação inicial: sem isto o painel só conhece sessões que ESTA janela
  // abriu, e a promessa da tela ("de todas as sessões") não se cumpre — um
  // processo que morreu numa sessão fechada não aparecia, que é o caso para o
  // qual o painel existe. Também é o que faz o botão Atualizar ter efeito no
  // estado vazio, que é justamente quando o usuário aperta.
  const visible = usePaneVisible()

  useEffect(() => {
    if (visible) {
      void refreshAllBackgroundProcesses()
    }
  }, [visible])

  // Só PROCESSO DE FUNDO vivo justifica poll de rede. Contar goal e subagente
  // aqui mantinha `process.list` batendo para sempre numa sessão que só tem um
  // /goal de pé. E o poll para quando o painel vira aba inativa — a política da
  // árvore de panes, que Agents e a seção de cron já seguem.
  const pollable = summary.groups.some(group =>
    group.items.some(item => item.type === 'background' && item.state === 'running')
  )

  useEffect(() => {
    if (!pollable || !visible) {
      return
    }

    const timer = setInterval(() => void refreshAllBackgroundProcesses(), POLL_MS)

    return () => clearInterval(timer)
  }, [pollable, visible])

  const [refreshing, setRefreshing] = useState(false)

  const refresh = async () => {
    setRefreshing(true)
    try {
      await refreshAllBackgroundProcesses()
      // As sessões conhecidas também são reconsultadas: um gateway antigo sem
      // `process.list_all` engole a chamada acima em silêncio, e sem isto o
      // botão não faria nada nessa instalação.
      await Promise.all(summary.groups.map(group => refreshBackgroundProcesses(group.runtimeId)))
    } finally {
      setRefreshing(false)
    }
  }

  const stop = async (runtimeId: string, item: ComposerStatusItem) => {
    try {
      await stopBackgroundProcess(runtimeId, item.id)
    } catch (error) {
      // A store já notifica em alguns caminhos; esta é a rede para o resto.
      // Falhar em silêncio deixaria o usuário achando que parou.
      notifyError(error, m.stopFailed)
    }
  }

  return (
    <div aria-label={m.aria} className="flex h-full min-h-0 flex-col" role="region">
      <div className="flex items-center justify-between gap-2 px-2 py-1.5">
        <SidebarPanelLabel>{m.title}</SidebarPanelLabel>
        <Tip label={m.refresh}>
          <Button
            aria-busy={refreshing}
            aria-label={m.refresh}
            disabled={refreshing}
            onClick={() => void refresh()}
            size="icon"
            variant="ghost"
          >
            <Codicon className={refreshing ? 'animate-spin' : undefined} name="refresh" />
          </Button>
        </Tip>
      </div>

      {summary.groups.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-1 px-6 text-center">
          <p className="text-sm text-(--ui-text-secondary)">{m.empty}</p>
          <p className="text-xs text-(--ui-text-quaternary)">{m.emptyBody}</p>
        </div>
      ) : (
        <>
          <p className="px-2 pb-1 text-xs text-(--ui-text-tertiary)">
            {m.summary(summary.running, summary.sessions)}
            {summary.failed > 0 ? ` · ${m.summaryFailed(summary.failed)}` : ''}
          </p>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {summary.groups.map(group => (
              <MissionGroupRows
                group={group}
                key={group.runtimeId}
                onDismiss={item => dismissBackgroundProcess(group.runtimeId, item.id)}
                onOpenSession={onOpenSession}
                onStop={item => void stop(group.runtimeId, item)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  )
}

interface MissionGroupRowsProps {
  group: MissionGroup
  onDismiss: (item: ComposerStatusItem) => void
  onOpenSession?: (storedId: string) => void
  onStop: (item: ComposerStatusItem) => void
}

function MissionGroupRows({ group, onDismiss, onOpenSession, onStop }: MissionGroupRowsProps) {
  const { t } = useI18n()
  const m = t.missionControl
  const canOpen = Boolean(group.storedId && onOpenSession)

  return (
    <section className="border-b border-(--ui-stroke-secondary) last:border-b-0">
      <button
        aria-label={canOpen ? `${group.title} — ${m.openSession}` : undefined}
        className={cn(
          'flex w-full items-baseline gap-2 px-2 py-1 text-left',
          canOpen ? 'hover:bg-(--ui-row-hover-background)' : 'cursor-default'
        )}
        disabled={!canOpen}
        onClick={() => group.storedId && onOpenSession?.(group.storedId)}
        type="button"
      >
        <span className="min-w-0 flex-1 truncate text-xs font-medium text-(--ui-text-primary)" title={group.title}>
          {group.title}
        </span>
        {group.failed > 0 ? (
          <span className="shrink-0 text-[0.65rem] text-(--dt-error, #f87171)">{m.groupFailed(group.failed)}</span>
        ) : null}
        {group.running > 0 ? (
          <span className="shrink-0 text-[0.65rem] text-(--ui-text-tertiary)">{m.groupRunning(group.running)}</span>
        ) : null}
      </button>

      <ul>
        {group.items.map(item => (
          <li className="flex items-center gap-2 px-2 py-1 hover:bg-(--ui-row-hover-background)" key={item.id}>
            <Codicon className={cn('shrink-0 text-xs', STATE_CLASS[item.state])} name={TYPE_ICON[item.type]} />
            {/* O estado NÃO pode ser comunicado só por cor: o Codicon é sempre
                aria-hidden, então sem este texto um leitor de tela lê "npm run
                build" e "pytest -q" sem saber qual delas morreu. */}
            <span className="sr-only">{STATE_LABEL(m, item.state)}</span>
            <span className="min-w-0 flex-1 truncate text-xs text-(--ui-text-secondary)" title={item.title}>
              {item.title}
            </span>
            {item.exitCode !== undefined && item.state === 'failed' ? (
              <span className="shrink-0 font-mono text-[0.65rem] text-(--dt-error, #f87171)">
                {m.exit(item.exitCode)}
              </span>
            ) : null}
            {canStop(item) ? (
              <Tip label={m.stop}>
                <Button aria-label={m.stop} onClick={() => onStop(item)} size="icon" variant="ghost">
                  <Codicon name="debug-stop" />
                </Button>
              </Tip>
            ) : null}
            {canDismiss(item) ? (
              <Tip label={m.dismiss}>
                <Button aria-label={m.dismiss} onClick={() => onDismiss(item)} size="icon" variant="ghost">
                  <Codicon name="close" />
                </Button>
              </Tip>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  )
}
