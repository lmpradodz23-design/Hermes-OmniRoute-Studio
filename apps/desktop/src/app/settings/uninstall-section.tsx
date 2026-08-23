import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import type { DesktopUninstallMode, DesktopUninstallSummary } from '@/global'
import { useI18n } from '@/i18n'
import { AlertTriangle, Loader2, Trash2 } from '@/lib/icons'
import { cn } from '@/lib/utils'

import { SectionHeading } from './primitives'

interface ModeOption {
  key: 'full' | 'gui' | 'lite'
  mode: DesktopUninstallMode
  /** Shown in the confirm step so people know exactly what disappears. */
  /** True when the option removes the Python agent (hidden if no agent). */
  needsAgent: boolean
}

const OPTIONS: ModeOption[] = [
  { mode: 'gui', key: 'gui', needsAgent: false },
  { mode: 'lite', key: 'lite', needsAgent: true },
  // full remove o agente (e os dados do usuário), então é uma opção que mexe no
  // agente: escondida num cliente lite sem agente local, igual à lite. Um lite
  // conectado a um backend remoto não tem agente NEM dados locais instalados
  // pela GUI, então gui-only é a opção correta (e a única) ali.
  { mode: 'full', key: 'full', needsAgent: true }
]

export function UninstallSection() {
  const { t } = useI18n()
  const u = t.settings.uninstall
  const [summary, setSummary] = useState<DesktopUninstallSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [pending, setPending] = useState<DesktopUninstallMode | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    const bridge = window.hermesDesktop?.uninstall

    if (!bridge) {
      setLoading(false)

      return
    }

    void bridge
      .summary()
      .then(result => {
        if (alive) {
          setSummary(result)
        }
      })
      .catch(() => {
        // Non-fatal — we degrade to offering the GUI-only option.
      })
      .finally(() => {
        if (alive) {
          setLoading(false)
        }
      })

    return () => {
      alive = false
    }
  }, [])

  const bridge = window.hermesDesktop?.uninstall

  if (!bridge) {
    return null
  }

  // Gate the agent-removing options on whether an agent is actually present.
  // A future lite client that ships without the bundled agent shows GUI-only.
  const agentInstalled = summary?.agent_installed ?? false
  const visibleOptions = OPTIONS.filter(opt => agentInstalled || !opt.needsAgent)

  const handleConfirm = async () => {
    if (!pending) {
      return
    }

    setRunning(true)
    setError(null)

    try {
      const result = await bridge.run(pending)

      if (!result.ok) {
        setError(result.message || result.error || 'Uninstall could not start.')
        setRunning(false)
        setPending(null)
      }
      // On success the app quits shortly; keep the spinner up until it does.
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setRunning(false)
      setPending(null)
    }
  }

  const pendingOption = OPTIONS.find(opt => opt.mode === pending) ?? null

  return (
    <div className="mx-auto mt-8 w-full max-w-2xl">
      <SectionHeading icon={AlertTriangle} title={u.dangerZone} />

      <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3">
        {loading ? (
          <div className="flex items-center gap-2 py-2 text-sm text-muted-foreground">
            <Loader2 className="size-3.5 animate-spin" />
            {u.checking}
          </div>
        ) : pendingOption ? (
          <div>
            <p className="text-sm font-medium text-destructive">{u.confirmTitle}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {u.confirmBody(u[`${pendingOption.key}Consequence`])}
            </p>
            {summary?.running_app_path && (
              <p className="mt-1 font-mono text-[0.68rem] text-muted-foreground/60">{u.appPath(summary.running_app_path)}</p>
            )}
            {error && <p className="mt-2 text-xs text-destructive">{error}</p>}
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <Button disabled={running} onClick={() => void handleConfirm()} size="sm" variant="destructive">
                {running && <Loader2 className="size-3 animate-spin" />}
                {running ? u.running : u.confirm}
              </Button>
              <Button disabled={running} onClick={() => setPending(null)} size="sm" variant="text">
                {t.common.cancel}
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            <p className="text-sm font-medium">{u.heading}</p>
            <p className="text-xs text-muted-foreground">{u.intro}</p>
            <div className="mt-1 flex flex-col gap-2">
              {visibleOptions.map(opt => (
                <button
                  className={cn(
                    'flex items-start gap-3 rounded-lg border border-border/60 bg-background/40 px-3 py-2.5 text-left transition',
                    'hover:border-destructive/40 hover:bg-destructive/5'
                  )}
                  key={opt.mode}
                  onClick={() => {
                    setError(null)
                    setPending(opt.mode)
                  }}
                  type="button"
                >
                  <Trash2 className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-foreground">{u[`${opt.key}Title`]}</span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">{u[`${opt.key}Description`]}</span>
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
