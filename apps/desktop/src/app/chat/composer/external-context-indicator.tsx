import { useState } from 'react'

import { useI18n } from '@/i18n'

export type ExternalContextStatus = {
  active: boolean
  detail: string | null
  source: 'external-file' | 'installed-skill' | 'mcp-external' | 'memory' | 'web' | null
  turnsAgo: number | null
}

export function ExternalContextIndicator({ status }: { status: ExternalContextStatus }) {
  const { t } = useI18n()
  const [expanded, setExpanded] = useState(false)

  if (!status.active || !status.source || status.turnsAgo === null) {
    return null
  }

  return (
    <div
      aria-live="polite"
      className="rounded-lg border border-amber-500/35 bg-amber-500/8 px-2 py-1 text-[0.68rem] text-amber-900 dark:text-amber-200"
      role="status"
    >
      <button
        aria-expanded={expanded}
        aria-label={expanded ? t.composer.externalContextHide : t.composer.externalContextShow}
        className="flex w-full items-center gap-1.5 text-left"
        onClick={() => setExpanded(value => !value)}
        type="button"
      >
        <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-amber-500" />
        <span>{t.composer.externalContextActive(status.turnsAgo)}</span>
      </button>
      {expanded && (
        <div className="mt-1 truncate text-[0.64rem] text-muted-foreground">
          {t.composer.externalContextDetails(
            t.composer.externalContextSources[status.source],
            status.detail ?? t.composer.externalContextUnavailable
          )}
        </div>
      )}
    </div>
  )
}
