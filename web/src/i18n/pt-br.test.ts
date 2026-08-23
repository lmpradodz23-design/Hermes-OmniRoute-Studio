// @vitest-environment node
/**
 * Português do Brasil — o portão que impede a tradução de apodrecer.
 *
 * O catálogo `pt` deste projeto é português EUROPEU. Isso não aparece em
 * nenhuma métrica de cobertura: `pt` está em 94,4% e mesmo assim um brasileiro
 * lê "Guardar", "A carregar…", "ficheiro", "registo" e "separador". Cobertura
 * mede quantas strings foram traduzidas, não para qual português.
 *
 * `pt-br.ts` herda de `pt` e sobrescreve só o que muda. Estes testes garantem
 * as duas propriedades que importam:
 *
 *   1. **Nenhuma chave falta.** Chave ausente cai no texto em inglês escrito no
 *      próprio JSX (`p.activeProfile ?? "Active profile"`), então o usuário vê
 *      inglês no meio do português — e nada quebra para avisar.
 *   2. **Nenhum lusitanismo sobra.** A varredura roda sobre o catálogo FINAL,
 *      depois do merge, e não sobre a lista de overrides: foi assim que a
 *      segunda leva de 16 apareceu, invisível na primeira passada.
 */

import { describe, expect, it } from 'vitest'

import { en } from './en'
import { pt } from './pt'
import { ptBr } from './pt-br'

/**
 * Chaves cujo texto em pt-BR é DELIBERADAMENTE idêntico ao inglês: nomes
 * próprios (Hermes Agent, Nous Research, Telegram, Discord, Slack), termos que
 * o mercado brasileiro usa em inglês (Chat, Cron, Plugins, Prompt, Tokens,
 * Gateway, Slug, Tenant), caminhos, e placeholders de cron.
 *
 * Uma chave nova em inglês que não esteja aqui falha o teste PELO NOME.
 */
const INTENTIONALLY_IDENTICAL = new Set([
  "common.msgs",
  "common.gateway",
  "app.brand",
  "app.brandShort",
  "app.footer.org",
  "app.nav.chat",
  "app.nav.cron",
  "app.nav.plugins",
  "app.pluginNavSection",
  "app.webUi",
  "status.gateway",
  "status.pid",
  "analytics.total",
  "analytics.tokens",
  "models.tokens",
  "cron.prompt",
  "cron.schedulePlaceholder",
  "cron.scheduleModes.customPlaceholder",
  "cron.scheduleDescribe.none",
  "cron.delivery.local",
  "cron.delivery.telegram",
  "cron.delivery.discord",
  "cron.delivery.slack",
  "cron.delivery.email",
  "profiles.hasEnv",
  "pluginsPage.updateGit",
  "config.configPath",
  "config.categories.terminal",
  "config.categories.discord",
  "achievements.hero.kicker",
  "achievements.hero.title",
  "achievements.stats.highest_tier_hint",
  "achievements.share.tweet_text",
  "kanban.slug",
  "kanban.tenant",
  "kanban.specifier",
  "kanban.logAt",
  "kanban.skillsLabel",
])

/**
 * Formas de português europeu. Cada uma foi encontrada no catálogo real, não
 * imaginada. Se uma tradução nova trouxer qualquer delas, o teste aponta a
 * chave e o trecho.
 */
const EUROPEAN_PORTUGUESE = [
  /\bA (guardar|carregar|criar|executar|iniciar|reiniciar|atualizar|enviar|fechar|construir|processar|gerar)\b/i,
  /\bguardar\b/i,
  /\bguardad[oa]s?\b/i,
  /\bficheiros?\b/i,
  /\bregistos?\b/i,
  /\becr[ãa]s?\b/i,
  /\butilizador(es)?\b/i,
  /\bseparador(es)?\b/i,
  /\bintroduz(a|ir)\b/i,
  /\b(iniciar|inicie) sess[ãa]o\b/i,
  /\ba mostrar\b/i,
  /\bdetetar?\b/i,
  /\btelem[óo]ve(l|is)\b/i,
  /\bequipa\b/i,
  /\bcontactos?\b/i,
]

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

describe('locale pt-BR', () => {
  const english = flatten(en)
  const european = flatten(pt)
  const brazilian = flatten(ptBr)

  it('cobre toda chave que existe em inglês', () => {
    const missing = [...english.keys()].filter(key => !brazilian.has(key))

    expect(
      missing,
      `Estas chaves não existem em pt-BR. O componente cai no texto em inglês ` +
        `escrito no JSX e o usuário vê inglês no meio do português:\n  ${missing.join('\n  ')}`
    ).toEqual([])
  })

  it('não deixa nenhuma forma de português europeu passar', () => {
    const offenders: string[] = []

    for (const [key, text] of brazilian) {
      const pattern = EUROPEAN_PORTUGUESE.find(rule => rule.test(text))

      if (pattern) {
        offenders.push(`  ${key}: ${JSON.stringify(text).slice(0, 90)}  (${pattern})`)
      }
    }

    expect(
      offenders,
      `Português europeu em pt-BR. Traduza para a forma brasileira ` +
        `(guardar→salvar, ficheiro→arquivo, registo→registro, separador→aba, ` +
        `utilizador→usuário, "A carregar…"→"Carregando…"):\n${offenders.join('\n')}`
    ).toEqual([])
  })

  it('traduz tudo que não está na lista revisada de idênticos', () => {
    const identical = [...english]
      .filter(([key, value]) => brazilian.get(key) === value)
      .map(([key]) => key)

    const unreviewed = identical.filter(key => !INTENTIONALLY_IDENTICAL.has(key))

    expect(
      unreviewed,
      `Estas chaves estão em inglês na interface pt-BR. Traduza, ou — se o texto ` +
        `deve mesmo ficar idêntico — acrescente a INTENTIONALLY_IDENTICAL com o ` +
        `motivo:\n  ${unreviewed.join('\n  ')}`
    ).toEqual([])
  })

  it('mantém a lista de idênticos honesta', () => {
    const stale = [...INTENTIONALLY_IDENTICAL].filter(
      key => english.has(key) && brazilian.get(key) !== english.get(key)
    )

    expect(stale, `Traduzidas mas ainda listadas como idênticas:\n  ${stale.join('\n  ')}`).toEqual([])

    const gone = [...INTENTIONALLY_IDENTICAL].filter(key => !english.has(key))

    expect(gone, `Chaves que não existem mais em en.ts:\n  ${gone.join('\n  ')}`).toEqual([])
  })

  it('de fato diverge do português europeu onde precisa divergir', () => {
    // Sem esta checagem, um pt-BR que só reexportasse `pt` passaria em tudo
    // acima e não teria feito nada.
    const divergences = [...brazilian].filter(([key, text]) => european.get(key) !== text)

    expect(divergences.length).toBeGreaterThan(60)

    expect(ptBr.common.save).toBe('Salvar')
    expect(ptBr.common.saving).toBe('Salvando…')
    expect(ptBr.logs.file).toBe('Arquivo')
    expect(ptBr.logs.title).toBe('Registros')
    expect(pt.common.save).toBe('Guardar')
  })

  it('é registrado como locale utilizável', () => {
    expect(ptBr).toBeTruthy()
    expect(Object.keys(ptBr).length).toBeGreaterThan(5)
  })
})
