/**
 * POLÍTICA DE CACHE DO SERVICE WORKER — a parte que decide, isolada da parte
 * que executa.
 *
 * Vive em um arquivo próprio, carregado por `sw.js` via `importScripts`, por
 * um motivo só: assim `sw-policy.test.ts` roda estas decisões no vitest sem
 * precisar de um ambiente de service worker. Uma política de cache que nunca
 * foi testada é uma suposição, e neste produto a suposição errada vaza sessão.
 *
 * ── A REGRA QUE NÃO SE NEGOCIA ──────────────────────────────────────────────
 *
 * Nada que carregue credencial entra no Cache Storage. Em concreto:
 *
 *  1. `/api/**` — resposta de API é dado de sessão. Cachear transforma dado de
 *     sessão em dado persistente no dispositivo, legível por qualquer script
 *     na origem e sobrevivente ao logout. NUNCA.
 *
 *  2. **Navegações (o próprio `index.html`)** — este é o caso que a maioria
 *     das receitas de PWA erra, e que aqui seria grave. O servidor Python
 *     (`hermes_cli/web_server.py`) injeta um token de sessão de uso único no
 *     HTML a cada render: `window.__HERMES_SESSION_TOKEN__ = "…"`. Um
 *     `navigateFallback` com `index.html` no precache — o padrão do
 *     `vite-plugin-pwa` e do Workbox — congelaria ESSE token no disco do
 *     dispositivo e o serviria em toda abertura seguinte. Duas consequências,
 *     ambas ruins: um segredo de uso único vira um segredo persistente, e o
 *     app passa a abrir com um token morto e 401 em tudo.
 *
 *     Foi por isso que este service worker é escrito à mão em vez de gerado.
 *
 *  3. Qualquer requisição que não seja GET, e qualquer origem diferente.
 *
 * O que ENTRA no cache é só o que é imutável e público: os bundles com hash no
 * nome (`/assets/index-Bt0yKstu.js`), fontes, ícones e o manifest. Um arquivo
 * com hash no nome nunca muda de conteúdo — ele é substituído por outro nome.
 *
 * ── CONSEQUÊNCIA ASSUMIDA ───────────────────────────────────────────────────
 *
 * Como `index.html` nunca é cacheado, o app **não abre offline**. Offline, a
 * navegação cai em `/offline.html`, que explica que o gateway está inalcançável.
 * Isso é pior do que um shell offline e é deliberado: a alternativa exigiria
 * persistir o HTML que carrega o token. Entre "abre offline" e "não guarda
 * segredo no disco", o segundo ganha.
 */
;(function attachPolicy(scope) {
  'use strict'

  /** Prefixos que nunca podem ser cacheados: carregam ou consomem sessão. */
  var NEVER_CACHE_PREFIXES = ['/api/', '/dashboard-plugins/', '/login', '/logout', '/oauth/']

  /** Prefixos imutáveis e públicos. Conteúdo endereçado por hash ou estático. */
  var CACHEABLE_PREFIXES = ['/assets/', '/fonts/', '/fonts-terminal/', '/icons/']

  /** Caminhos exatos, estáticos e sem segredo. */
  var CACHEABLE_EXACT = ['/favicon.ico', '/manifest.webmanifest', '/offline.html']

  /**
   * O dashboard pode ser servido sob um prefixo quando está atrás de um proxy
   * reverso — o backend Python injeta `window.__HERMES_BASE_PATH__` a partir do
   * `X-Forwarded-Prefix`. Sem descontar esse prefixo aqui, `/hermes/api/status`
   * não casaria com `/api/` e cairia no default. O default fecha, então não
   * viraria cache — mas `/hermes/assets/…` também não casaria com `/assets/` e
   * o cache pararia de funcionar por inteiro, em silêncio. Descontar o prefixo
   * mantém as duas metades corretas.
   */
  function relativePath(pathname, basePath) {
    var base = basePath || ''

    if (!base || base === '/') {
      return pathname
    }

    base = base.charAt(0) === '/' ? base : '/' + base
    base = base.replace(/\/+$/, '')

    if (pathname === base) {
      return '/'
    }

    if (pathname.indexOf(base + '/') === 0) {
      return pathname.slice(base.length)
    }

    return pathname
  }

  function startsWithAny(pathname, prefixes) {
    for (var i = 0; i < prefixes.length; i += 1) {
      if (pathname.indexOf(prefixes[i]) === 0) {
        return true
      }
    }

    return false
  }

  /**
   * @param {string} rawUrl        URL absoluta da requisição.
   * @param {object} request       { method, mode, origin, basePath } — o
   *                               subconjunto do Request que a decisão usa,
   *                               mais o prefixo sob o qual o app é servido.
   * @returns {'cache-first'|'navigate'|'network-only'}
   */
  function strategyFor(rawUrl, request) {
    var method = (request && request.method) || 'GET'
    var mode = (request && request.mode) || 'no-cors'
    var origin = (request && request.origin) || ''
    var basePath = (request && request.basePath) || ''

    var url
    try {
      url = new URL(rawUrl)
    } catch (_error) {
      return 'network-only'
    }

    // Navegação: sempre rede. O HTML carrega o token de uso único.
    if (mode === 'navigate') {
      return 'navigate'
    }

    // Só GET pode ser cacheado, e só na própria origem.
    if (method !== 'GET') {
      return 'network-only'
    }

    if (origin && url.origin !== origin) {
      return 'network-only'
    }

    var pathname = relativePath(url.pathname, basePath)

    if (startsWithAny(pathname, NEVER_CACHE_PREFIXES)) {
      return 'network-only'
    }

    if (CACHEABLE_EXACT.indexOf(pathname) !== -1) {
      return 'cache-first'
    }

    if (startsWithAny(pathname, CACHEABLE_PREFIXES)) {
      return 'cache-first'
    }

    // Default fecha: o que a política não reconheceu explicitamente vai à rede
    // e não fica no disco.
    return 'network-only'
  }

  scope.HermesSwPolicy = {
    CACHEABLE_EXACT: CACHEABLE_EXACT,
    CACHEABLE_PREFIXES: CACHEABLE_PREFIXES,
    NEVER_CACHE_PREFIXES: NEVER_CACHE_PREFIXES,
    relativePath: relativePath,
    strategyFor: strategyFor
  }
})(typeof self === 'undefined' ? this : self)
