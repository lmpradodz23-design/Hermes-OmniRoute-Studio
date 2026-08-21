import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { I18nProvider } from '@/i18n'

import { Intro } from './intro'

describe('Intro', () => {
  afterEach(cleanup)

  it('shows Brazilian Portuguese onboarding copy when pt-BR is active', () => {
    render(
      <I18nProvider configClient={null} initialLocale="pt-BR">
        <Intro seed={0} />
      </I18nProvider>
    )

    expect(screen.getByLabelText('HERMES AGENT')).toBeTruthy()
    expect(
      screen.getByText(/Envie um erro|Traga o problema|Envie o contexto/).textContent
    ).not.toContain('Drop a file path')
  })
})
