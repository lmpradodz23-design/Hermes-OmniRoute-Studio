import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/i18n', () => ({
  useI18n: () => ({
    t: {
      composer: {
        externalContextActive: (turns: number) => `Contexto externo ativo · ${turns} turno`,
        externalContextDetails: (source: string, detail: string) => `${source}: ${detail}`,
        externalContextHide: 'Ocultar origem',
        externalContextShow: 'Ver origem',
        externalContextSources: { web: 'web' },
        externalContextUnavailable: 'indisponível'
      }
    }
  })
}))

import { ExternalContextIndicator } from './external-context-indicator'

afterEach(cleanup)

describe('ExternalContextIndicator', () => {
  it('shows the active window and reveals the redacted source on demand', () => {
    render(
      <ExternalContextIndicator
        status={{
          active: true,
          detail: 'https://example.test/reference',
          source: 'web',
          turnsAgo: 1
        }}
      />
    )

    expect(screen.getByRole('status').textContent).toContain('Contexto externo ativo · 1 turno')
    expect(screen.queryByText(/example\.test/)).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Ver origem' }))

    expect(screen.getByText('web: https://example.test/reference')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Ocultar origem' }).getAttribute('aria-expanded')).toBe('true')
  })

  it('renders nothing when there is no active taint', () => {
    const { container } = render(
      <ExternalContextIndicator status={{ active: false, detail: null, source: null, turnsAgo: null }} />
    )

    expect(container.childElementCount).toBe(0)
  })
})
