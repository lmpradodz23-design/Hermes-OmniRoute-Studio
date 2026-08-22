import { describe, expect, it } from 'vitest'

import { en } from './en'
import { ptBr } from './pt-br'

/**
 * Chaves cujo texto em pt-BR é DELIBERADAMENTE idêntico ao inglês.
 *
 * Esta lista é o ponto inteiro deste arquivo. Um teste de percentual - "cobre
 * pelo menos 90%" - passa alegremente enquanto a tradução apodrece de 98% para
 * 90%, e nunca diz QUAL chave regrediu. Com a lista explícita, adicionar uma
 * chave nova sem traduzir falha o teste PELO NOME DA CHAVE, e traduzir uma
 * chave que estava aqui também falha - obrigando a remover a entrada e a
 * registrar a decisão.
 *
 * Cada entrada abaixo é uma decisão revisada, não um resto:
 *
 *  - Siglas e nomes próprios que não se traduzem: MCP, SSH, Hermes, Pro,
 *    Ultra, Cron, Webhooks, Plugins, Skills, Gateways, Layouts.
 *  - Termos que o mercado brasileiro usa em inglês: Local, Online, Offline,
 *    Host, Proxy URL, Webhook URL, web, git, pip.
 *  - Unidades e abreviações idênticas nos dois idiomas: MB, "d" (dia),
 *    "h" (hora), "A-Z", "0", ".".
 *  - Placeholders que são URLs de exemplo: trocá-los por um domínio "em
 *    português" só criaria exemplos que não existem.
 *  - preview.diff: DIFF é o termo que o próprio git imprime.
 *  - notifications.native.turnDoneBody: string vazia nos dois lados.
 */
const INTENTIONALLY_IDENTICAL = new Set([
  'notifications.native.turnDoneBody',
  'settings.nav.gateway',
  'settings.nav.mcp',
  'settings.nav.plugins',
  'settings.plugins.agent.sources.git',
  'settings.plugins.agent.sources.entrypoint',
  'settings.notifications.testTitle',
  'settings.config.attachmentSizeUnit',
  'settings.connections.kindLocal',
  'settings.connections.kindCloud',
  'settings.connections.kindSsh',
  'settings.gateway.sshHostTitle',
  'settings.gateway.sshHostPickTitle',
  'settings.model.tasks.mcp.label',
  'settings.omniroute.online',
  'settings.omniroute.offline',
  'skills.tabSkills',
  'skills.tabMcp',
  'skills.sortAlpha',
  'messaging.fieldCopy.TELEGRAM_PROXY.label',
  'messaging.fieldCopy.MATTERMOST_URL.placeholder',
  'messaging.fieldCopy.MATRIX_HOMESERVER.placeholder',
  'messaging.fieldCopy.SIGNAL_HTTP_URL.placeholder',
  'webhooks.webhookUrl',
  'profiles.renameDescSuffix',
  'artifacts.itemsLink',
  'artifacts.zero',
  'artifacts.colLocationLink',
  'sidebar.row.ageDay',
  'sidebar.row.ageHour',
  'composer.externalContextSources.web',
  'composer.urlPlaceholder',
  'composer.themeTryPost',
  'composer.url',
  'install.remoteUrlPlaceholder',
  'onboarding.pro',
  'shell.modelOptions.ultra',
  'shell.statusbar.cron',
  'shell.statusbar.webhooks',
  'shell.statusbar.contextUsagePanel.categories.mcp',
  'preview.diff',
  'zones.editTitle',
  'desktop.yoloTitle',
])

type Flat = Map<string, string>

function flatten(value: unknown, prefix = '', result: Flat = new Map()): Flat {
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

describe('Brazilian Portuguese locale', () => {
  const english = flatten(en)
  const portuguese = flatten(ptBr)

  it('has no missing keys', () => {
    const missing = [...english.keys()].filter(key => !portuguese.has(key))

    expect(missing, `chaves pt-BR ausentes: ${missing.join(', ')}`).toEqual([])
  })

  it('translates every string that is not on the reviewed identical list', () => {
    const identical = [...english]
      .filter(([key, value]) => portuguese.get(key) === value)
      .map(([key]) => key)

    const unreviewed = identical.filter(key => !INTENTIONALLY_IDENTICAL.has(key))

    expect(
      unreviewed,
      'Estas chaves estão em inglês na interface pt-BR. Traduza, ou - se o texto ' +
        'deve mesmo ficar idêntico - adicione a chave a INTENTIONALLY_IDENTICAL ' +
        `com o motivo no comentário do bloco:\n  ${unreviewed.join('\n  ')}`
    ).toEqual([])
  })

  it('keeps the identical list honest', () => {
    const stale = [...INTENTIONALLY_IDENTICAL].filter(
      key => english.has(key) && portuguese.get(key) !== english.get(key)
    )

    expect(
      stale,
      'Estas chaves foram traduzidas mas continuam listadas como idênticas. ' +
        `Remova de INTENTIONALLY_IDENTICAL:\n  ${stale.join('\n  ')}`
    ).toEqual([])

    const gone = [...INTENTIONALLY_IDENTICAL].filter(key => !english.has(key))

    expect(gone, `Chaves que não existem mais em en.ts:\n  ${gone.join('\n  ')}`).toEqual([])
  })

  it('reports coverage above 98%', () => {
    const translated = [...english].filter(([key, value]) => portuguese.get(key) !== value)
    const coverage = translated.length / english.size

    expect(
      coverage,
      `${translated.length}/${english.size} strings traduzidas (${(coverage * 100).toFixed(1)}%)`
    ).toBeGreaterThanOrEqual(0.98)
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

    for (const [translated, englishText] of translatedPairs) {
      expect(translated).not.toBe(englishText)
    }
  })

  it('localizes advanced settings copy and provider descriptions', () => {
    expect(ptBr.settings.fieldLabels.model).toBe('Modelo padrão')
    expect(ptBr.settings.fieldDescriptions.model).toContain('novas conversas')
    expect(ptBr.settings.fieldLabels['security.spendCeiling.sessionUsd']).toBe('Teto por sessão (US$)')
    expect(ptBr.settings.fieldLabels['security.localOnly']).toBe('Modo somente local')
    expect(ptBr.settings.fieldDescriptions['security.spendCeiling.sessionUsd']).toContain('somente pela interface')
    expect(ptBr.settings.fieldLabels['recording.enabled']).toBe('Gravação de sessão')
    expect(ptBr.settings.fieldDescriptions['recording.enabled']).toContain('desativada por padrão')
    expect(ptBr.settings.fieldLabels['capabilityPlane.providers.skills.mcp']).toBe('Skills do OmniRoute')
    expect(ptBr.settings.fieldDescriptions['capabilityPlane.mutationsRequireApproval']).toContain('confirmação')
    expect(ptBr.settings.providers.groupDescriptions?.OpenRouter).toContain('centenas de modelos')
    expect(ptBr.settings.omniroute.openDashboard).toBe('Abrir painel completo do OmniRoute')
  })

  it('translates the preview pane tab labels', () => {
    expect(ptBr.preview.source).toBe('FONTE')
    expect(ptBr.preview.renderedPreview).toBe('PRÉVIA')
  })
})
