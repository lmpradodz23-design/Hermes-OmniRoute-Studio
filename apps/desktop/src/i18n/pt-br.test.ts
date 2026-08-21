import { describe, expect, it } from 'vitest'

import { en } from './en'
import { ptBr } from './pt-br'

describe('Brazilian Portuguese locale', () => {
  it('covers at least 90% of the complete English string tree', () => {
    const flatten = (value: unknown, prefix = '', result = new Map<string, string>()) => {
      if (!value || typeof value !== 'object') {
        return result
      }

      for (const [key, child] of Object.entries(value)) {
        const path = prefix ? `${prefix}.${key}` : key

        if (typeof child === 'string') {
          result.set(path, child)
        } else if (child && typeof child === 'object' && !Array.isArray(child)) {
          flatten(child, path, result)
        }
      }

      return result
    }

    const english = flatten(en)
    const portuguese = flatten(ptBr)
    const missing = [...english.keys()].filter(key => !portuguese.has(key))
    const translated = [...english].filter(([key, value]) => portuguese.get(key) !== value)
    const coverage = translated.length / english.size

    expect(missing, `missing pt-BR keys: ${missing.join(', ')}`).toEqual([])
    expect(coverage, `${translated.length}/${english.size} translated strings`).toBeGreaterThanOrEqual(0.9)
  })

  it('does not fall back to English on the main desktop surfaces', () => {
    const translatedPairs = [
      [ptBr.common.apply, en.common.apply],
      [ptBr.fileMenu.copyPath, en.fileMenu.copyPath],
      [ptBr.boot.ready, en.boot.ready],
      [ptBr.sidebar.searchPlaceholder, en.sidebar.searchPlaceholder],
      [ptBr.composer.placeholderStarting, en.composer.placeholderStarting],
      [ptBr.settings.providers.connectAccount, en.settings.providers.connectAccount],
      [ptBr.settings.customEndpoints.title, en.settings.customEndpoints.title],
      [ptBr.onboarding.headerTitle, en.onboarding.headerTitle],
      [ptBr.errors.boundaryTitle, en.errors.boundaryTitle],
      [ptBr.ui.search.clear, en.ui.search.clear]
    ]

    for (const [translated, english] of translatedPairs) {
      expect(translated).not.toBe(english)
    }
  })

  it('localizes advanced settings copy and provider descriptions', () => {
    expect(ptBr.settings.fieldLabels.model).toBe('Modelo padrão')
    expect(ptBr.settings.fieldDescriptions.model).toContain('novas conversas')
    expect(ptBr.settings.providers.groupDescriptions?.OpenRouter).toContain('centenas de modelos')
    expect(ptBr.settings.omniroute.openDashboard).toBe('Abrir painel completo do OmniRoute')
  })
})
