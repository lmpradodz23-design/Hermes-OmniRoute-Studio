/**
 * SERVICE WORKER — a parte que executa. Quem DECIDE é `sw-policy.js`, que é
 * carregado aqui e testado em `web/src/pwa/sw-policy.test.ts`.
 *
 * Leia o cabeçalho de `sw-policy.js` antes de mexer aqui. O resumo:
 *   - `/api/**` e navegações NUNCA entram no Cache Storage;
 *   - só entra o que tem hash no nome ou é estático e público;
 *   - offline, a navegação cai em `/offline.html` em vez de tela branca.
 *
 * Escrito à mão, sem `vite-plugin-pwa`/Workbox, porque o `navigateFallback`
 * padrão dessas ferramentas precacheia `index.html` — e este `index.html`
 * carrega um token de sessão de uso único injetado pelo servidor Python.
 */

/* global importScripts, HermesSwPolicy */
// RELATIVO, como todo o resto deste arquivo. Absoluto, ele resolvia contra a
// raiz do host: servido sob um prefixo de proxy (/hermes/), dava 404 e a
// instalação do service worker abortava no topo do script — sem cache, sem
// página offline, e sem erro visível, porque isto roda antes do `install`.
importScripts('sw-policy.js')

// Troque a versão para invalidar tudo que ficou em disco. O nome carrega a
// versão, então um cache antigo some inteiro no `activate` em vez de conviver.
var CACHE_VERSION = 'hermes-pwa-v1'

// Único precache: o que precisa existir ANTES de a rede falhar. Nada aqui
// carrega segredo, e nenhum desses arquivos muda de conteúdo sem mudar de nome
// ou de versão de cache.
// Caminhos RELATIVOS de propósito: resolvem contra o escopo do service worker,
// então funcionam igual servidos na raiz ou sob um prefixo de proxy reverso.
var PRECACHE = ['offline.html', 'manifest.webmanifest', 'icons/icon-192.png', 'icons/icon-512.png']

self.addEventListener('install', function onInstall(event) {
  event.waitUntil(
    caches
      .open(CACHE_VERSION)
      .then(function fill(cache) {
        // `reload` para não semear o cache com uma cópia que o cache HTTP do
        // navegador já tinha guardado de uma versão anterior.
        return cache.addAll(
          PRECACHE.map(function asRequest(path) {
            return new Request(path, { cache: 'reload' })
          })
        )
      })
      // Um precache que falha não pode derrubar a instalação: o app funciona
      // sem service worker, e falhar aqui deixaria o usuário sem nenhum.
      .catch(function ignore() {})
      .then(function activateNow() {
        return self.skipWaiting()
      })
  )
})

self.addEventListener('activate', function onActivate(event) {
  event.waitUntil(
    caches
      .keys()
      .then(function dropOld(names) {
        return Promise.all(
          names.map(function maybeDelete(name) {
            return name === CACHE_VERSION ? null : caches.delete(name)
          })
        )
      })
      .then(function claim() {
        return self.clients.claim()
      })
  )
})

/**
 * Desinstalação remota. Se o service worker precisar ser desligado — bug,
 * incidente, mudança de política — publicar um `sw.js` que só faz isto não
 * basta: o antigo já está registrado nos dispositivos. Esta mensagem existe
 * para que o app possa mandá-lo embora sem esperar um novo deploy chegar.
 */
self.addEventListener('message', function onMessage(event) {
  if (!event || !event.data || event.data.type !== 'hermes:unregister') {
    return
  }

  event.waitUntil(
    caches
      .keys()
      .then(function purge(names) {
        return Promise.all(
          names.map(function drop(name) {
            return caches.delete(name)
          })
        )
      })
      .then(function unregister() {
        return self.registration.unregister()
      })
  )
})

function cacheFirst(request) {
  return caches.match(request).then(function hit(cached) {
    if (cached) {
      return cached
    }

    return fetch(request).then(function store(response) {
      // Só guarda resposta boa e da própria origem. `opaque` (cross-origin sem
      // CORS) não dá para inspecionar, então não entra.
      if (response && response.ok && response.type === 'basic') {
        var copy = response.clone()

        caches.open(CACHE_VERSION).then(function put(cache) {
          cache.put(request, copy)
        })
      }

      return response
    })
  })
}

function navigateOrOffline(request) {
  // Rede primeiro e SEMPRE — o HTML carrega o token de sessão de uso único.
  return fetch(request).catch(function offline() {
    return caches.match(new URL('offline.html', self.registration.scope).href).then(function fallback(page) {
      return (
        page ||
        new Response('<!doctype html><meta charset="utf-8"><title>Offline</title><p>Sem conexão com o gateway.', {
          headers: { 'Content-Type': 'text/html; charset=utf-8' },
          status: 503
        })
      )
    })
  })
}

/**
 * O prefixo sob o qual o app é servido, derivado do escopo do próprio registro.
 * Quando o dashboard está atrás de um proxy reverso, o registro acontece em
 * `/prefixo/sw.js` com escopo `/prefixo/`, e é daí que o prefixo sai — sem
 * depender de nenhuma variável injetada, que o service worker não enxerga.
 */
function basePath() {
  try {
    return new URL(self.registration.scope).pathname.replace(/\/+$/, '')
  } catch (_error) {
    return ''
  }
}

self.addEventListener('fetch', function onFetch(event) {
  var request = event.request
  var strategy = HermesSwPolicy.strategyFor(request.url, {
    basePath: basePath(),
    method: request.method,
    mode: request.mode,
    origin: self.location.origin
  })

  if (strategy === 'navigate') {
    event.respondWith(navigateOrOffline(request))

    return
  }

  if (strategy === 'cache-first') {
    event.respondWith(cacheFirst(request))

    return
  }

  // `network-only`: não chamamos `respondWith`, então o navegador faz a
  // requisição normalmente e o service worker sai do caminho por completo.
  // Isso é mais forte do que `fetch(request)` — nem o `event` toca a resposta.
})
