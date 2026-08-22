/**
 * Registro do service worker.
 *
 * Três coisas que este arquivo faz de propósito e que valem explicação:
 *
 * 1. **Não registra em dev.** O Vite dev server serve `index.html` próprio e o
 *    plugin `hermes:dev-session-token` raspa o token do backend a cada load.
 *    Um service worker no meio disso troca um bug de cache por horas de
 *    "por que minha mudança não aparece". Em dev o app é o app, sem camada.
 *
 * 2. **Não registra fora de contexto seguro.** `serviceWorker` só existe em
 *    HTTPS e em `localhost`. O caso real que isso cobre é o celular abrindo o
 *    gateway por `http://192.168.x.x` — ali `navigator.serviceWorker` é
 *    `undefined` e chamar direto seria um TypeError na inicialização do app.
 *
 * 3. **Tem interruptor.** `unregisterServiceWorker()` remove o registro e apaga
 *    todo o Cache Storage. Um service worker ruim se auto-perpetua: ele já está
 *    no aparelho e continua servindo mesmo enquanto o deploy novo sobe. Ter o
 *    desligamento pronto antes de precisar dele não é zelo, é a única forma de
 *    consertar sem pedir para o usuário limpar dados do site.
 */

/**
 * O dashboard pode ser servido sob um prefixo atrás de um proxy reverso; o
 * backend injeta `window.__HERMES_BASE_PATH__` a partir do `X-Forwarded-Prefix`.
 * Um service worker só controla o diretório de onde é servido, então registrar
 * `/sw.js` num app montado em `/hermes/` daria escopo `/` — que o navegador
 * recusa — ou controlaria o host inteiro, que não é nosso. O prefixo entra na
 * URL e no escopo.
 */
function basePath(): string {
  if (typeof window === 'undefined') {
    return ''
  }

  const raw = (window as { __HERMES_BASE_PATH__?: string }).__HERMES_BASE_PATH__ ?? ''

  if (!raw) {
    return ''
  }

  return (raw.startsWith('/') ? raw : `/${raw}`).replace(/\/+$/, '')
}

export function serviceWorkerUrl(base = basePath()): string {
  return `${base}/sw.js`
}

export function serviceWorkerScope(base = basePath()): string {
  return `${base}/`
}

export function serviceWorkerSupported(): boolean {
  return typeof navigator !== 'undefined' && 'serviceWorker' in navigator
}

/**
 * @param options.enabled  Sobrescreve a decisão automática. Passe `false` para
 *                         desligar sem remover a chamada.
 */
export async function registerServiceWorker(options?: {
  enabled?: boolean
}): Promise<ServiceWorkerRegistration | null> {
  const enabled = options?.enabled ?? !import.meta.env.DEV

  if (!enabled || !serviceWorkerSupported()) {
    return null
  }

  try {
    return await navigator.serviceWorker.register(serviceWorkerUrl(), { scope: serviceWorkerScope() })
  } catch (error) {
    // Falhar aqui não pode derrubar o app: o Hermes funciona inteiro sem
    // service worker, que só acrescenta instalabilidade e a página offline.
    console.warn('[hermes] service worker não registrou:', error)

    return null
  }
}

/**
 * Desliga o service worker e apaga tudo que ele guardou. Exposto em
 * `window.__hermesUnregisterServiceWorker` para poder ser chamado do console
 * do dispositivo quando o app já está quebrado a ponto de não ter interface.
 */
export async function unregisterServiceWorker(): Promise<boolean> {
  if (!serviceWorkerSupported()) {
    return false
  }

  let removed = false

  try {
    const registrations = await navigator.serviceWorker.getRegistrations()

    for (const registration of registrations) {
      removed = (await registration.unregister()) || removed
    }

    if (typeof caches !== 'undefined') {
      const names = await caches.keys()

      await Promise.all(names.map(name => caches.delete(name)))
    }
  } catch (error) {
    console.warn('[hermes] falha ao remover o service worker:', error)
  }

  return removed
}

export function exposeServiceWorkerKillSwitch(target: Record<string, unknown> = window as never): void {
  target.__hermesUnregisterServiceWorker = unregisterServiceWorker
}
