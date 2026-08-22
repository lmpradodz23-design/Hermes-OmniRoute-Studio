/**
 * A política de cache do service worker, testada de verdade.
 *
 * `public/sw-policy.js` é um script clássico (o service worker o carrega com
 * `importScripts`), então aqui ele é lido do disco e avaliado com um `self`
 * falso. É de propósito: o arquivo testado é EXATAMENTE o arquivo publicado,
 * não uma cópia em TypeScript que pode divergir dele em silêncio.
 *
 * O que estes testes protegem é uma coisa só: nada que carregue credencial
 * pode entrar no Cache Storage. Ver o cabeçalho de `public/sw-policy.js`.
 */

import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

type Strategy = 'cache-first' | 'navigate' | 'network-only'

interface RequestShape {
  basePath?: string
  method?: string
  mode?: string
  origin?: string
}

interface Policy {
  CACHEABLE_EXACT: string[]
  CACHEABLE_PREFIXES: string[]
  NEVER_CACHE_PREFIXES: string[]
  relativePath: (pathname: string, basePath: string) => string
  strategyFor: (url: string, request: RequestShape) => Strategy
}

function loadPolicy(): Policy {
  const here = path.dirname(fileURLToPath(import.meta.url))
  const source = readFileSync(path.resolve(here, '../../public/sw-policy.js'), 'utf8')
  const scope: Record<string, unknown> = {}

  new Function('self', source)(scope)

  return scope.HermesSwPolicy as Policy
}

const policy = loadPolicy()
const ORIGIN = 'https://hermes.local'
const navigation: RequestShape = { method: 'GET', mode: 'navigate', origin: ORIGIN }
const get: RequestShape = { method: 'GET', mode: 'cors', origin: ORIGIN }

describe('política de cache do service worker', () => {
  describe('nunca cacheia nada com credencial', () => {
    const mustNeverCache = [
      // Resposta de API é dado de sessão.
      '/api/status',
      '/api/config',
      '/api/sessions',
      '/api/gateway/events',
      '/api/providers/oauth/openai/start',
      '/api/model/options',
      // Scripts de plugin são servidos pelo mesmo servidor autenticado.
      '/dashboard-plugins/kanban.js',
      // Fluxo de login.
      '/login',
      '/logout',
      '/oauth/callback'
    ]

    it.each(mustNeverCache)('%s vai à rede e não fica em disco', pathname => {
      expect(policy.strategyFor(`${ORIGIN}${pathname}`, get)).toBe('network-only')
    })
  })

  describe('navegação nunca é cacheada', () => {
    // Este é o caso que a maioria das receitas de PWA erra. O servidor Python
    // injeta `window.__HERMES_SESSION_TOKEN__` no HTML a cada render; um
    // `navigateFallback` com index.html precacheado congelaria esse token de
    // uso único no disco do aparelho.
    const routes = ['/', '/chat', '/sessions', '/skills', '/config', '/qualquer/rota/do/spa']

    it.each(routes)('%s usa a estratégia de navegação (rede, com fallback offline)', route => {
      expect(policy.strategyFor(`${ORIGIN}${route}`, navigation)).toBe('navigate')
    })

    it('index.html pedido como navegação também não vira cache-first', () => {
      expect(policy.strategyFor(`${ORIGIN}/index.html`, navigation)).toBe('navigate')
    })
  })

  describe('cacheia o que é imutável e público', () => {
    const cacheable = [
      '/assets/index-Bt0yKstu.js',
      '/assets/react-vendor-CG1dQPxS.js',
      '/assets/ChatPage-D3WRTCQL.js',
      '/assets/index-abc123.css',
      '/fonts/inter.woff2',
      '/fonts-terminal/mono.woff2',
      '/icons/icon-192.png',
      '/icons/icon-maskable-512.png',
      '/favicon.ico',
      '/manifest.webmanifest',
      '/offline.html'
    ]

    it.each(cacheable)('%s pode ficar em cache', pathname => {
      expect(policy.strategyFor(`${ORIGIN}${pathname}`, get)).toBe('cache-first')
    })
  })

  describe('fecha por padrão', () => {
    it('caminho não reconhecido vai à rede', () => {
      expect(policy.strategyFor(`${ORIGIN}/algo-novo-que-ninguem-previu`, get)).toBe('network-only')
    })

    it('outra origem nunca é cacheada, mesmo com caminho cacheável', () => {
      expect(policy.strategyFor('https://cdn.exemplo.com/assets/x.js', get)).toBe('network-only')
    })

    it.each(['POST', 'PUT', 'PATCH', 'DELETE'])('%s nunca é cacheado', method => {
      expect(policy.strategyFor(`${ORIGIN}/assets/x.js`, { ...get, method })).toBe('network-only')
    })

    it('URL que não parseia vai à rede em vez de explodir', () => {
      expect(policy.strategyFor('isto-nao-e-uma-url', get)).toBe('network-only')
    })
  })

  describe('a própria lista de prefixos', () => {
    it('não deixa um prefixo cacheável cobrir um prefixo proibido', () => {
      for (const cacheable of policy.CACHEABLE_PREFIXES) {
        for (const forbidden of policy.NEVER_CACHE_PREFIXES) {
          expect(
            forbidden.startsWith(cacheable),
            `"${cacheable}" cobriria "${forbidden}" — a ordem das regras deixaria de proteger`
          ).toBe(false)
        }
      }
    })

    it('/api/ está na lista proibida', () => {
      expect(policy.NEVER_CACHE_PREFIXES).toContain('/api/')
    })

    it('nenhum caminho exato cacheável é uma página HTML do app', () => {
      for (const exact of policy.CACHEABLE_EXACT) {
        expect(exact).not.toBe('/')
        expect(exact).not.toBe('/index.html')
      }
    })
  })

  describe('atrás de um proxy reverso (base path)', () => {
    // O backend Python injeta `__HERMES_BASE_PATH__` a partir do
    // `X-Forwarded-Prefix`. Sem descontar o prefixo, `/hermes/assets/x.js`
    // deixaria de casar com `/assets/` e o cache morreria em silêncio — e o
    // que é pior, um prefixo malicioso poderia fazer `/x/api/` parecer um
    // caminho comum. As duas metades precisam continuar corretas.
    const proxied: RequestShape = { basePath: '/hermes', method: 'GET', mode: 'cors', origin: ORIGIN }

    it('não cacheia /hermes/api/**', () => {
      expect(policy.strategyFor(`${ORIGIN}/hermes/api/status`, proxied)).toBe('network-only')
    })

    it('continua cacheando /hermes/assets/**', () => {
      expect(policy.strategyFor(`${ORIGIN}/hermes/assets/index-abc.js`, proxied)).toBe('cache-first')
    })

    it('cacheia /hermes/offline.html', () => {
      expect(policy.strategyFor(`${ORIGIN}/hermes/offline.html`, proxied)).toBe('cache-first')
    })

    it('um caminho fora do prefixo não é reescrito e cai no default', () => {
      expect(policy.strategyFor(`${ORIGIN}/outro/assets/x.js`, proxied)).toBe('network-only')
    })

    it('um caminho que só COMEÇA com o prefixo não conta como dentro dele', () => {
      // `/hermesbot/assets/x.js` não está sob `/hermes/`.
      expect(policy.strategyFor(`${ORIGIN}/hermesbot/assets/x.js`, proxied)).toBe('network-only')
    })

    it('relativePath é estável nos casos de borda', () => {
      expect(policy.relativePath('/hermes/api/x', '/hermes')).toBe('/api/x')
      expect(policy.relativePath('/hermes', '/hermes')).toBe('/')
      expect(policy.relativePath('/api/x', '')).toBe('/api/x')
      expect(policy.relativePath('/api/x', '/')).toBe('/api/x')
      expect(policy.relativePath('/hermes/api/x', 'hermes')).toBe('/api/x')
      expect(policy.relativePath('/hermes/api/x', '/hermes/')).toBe('/api/x')
    })
  })
})
