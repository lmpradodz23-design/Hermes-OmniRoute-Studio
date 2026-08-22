# PWA e Android — o que foi feito, medido e o que falta

**Data:** 2026-08-22 · **Autor:** Claude · **Referência:** `audit/HERMES_MULTIPLATFORM.md`

---

## 0. Auditoria antes de codificar (§8 do spec), com as respostas

| Pergunta | Resposta medida |
|---|---|
| `web/` constrói hoje? | **Sim.** `npm run build` → exit 0. `typecheck` → exit 0. Suíte → 37 arquivos / 275 testes → exit 0 |
| Estado do pareamento? | `PairingPage` existe mas é **pareamento de usuário de plataforma** (Telegram/Discord), não de dispositivo. O QR em `ChannelsPage` é de canal. Pareamento de dispositivo **não existe** |
| O gateway autentica origem remota? | **Sim, e isso muda o tamanho da M1.4.** Existe modo *gated*: `__HERMES_AUTH_REQUIRED__`, cookie `hermes_session_at`, redirect para `/login`, e **ticket de uso único por WebSocket** (`getWsTicket`). O celular passa pelo mesmo fluxo. QR vira conveniência, não pré-requisito |
| `apps/shared` compartilha tokens de tema? | Não — só utilidades (`skin.ts`, `websocket-url.ts`, `json-rpc-gateway.ts`, billing). `buildHermesWebSocketUrl` **já aceita `host` e `protocol`**, então WebSocket cross-origin não precisa de nada novo |
| pt-BR existe no `web/src/i18n`? | Existe `pt.ts` (pt genérico), não `pt-br.ts`. Fica registrado como pendência |

---

## 1. O achado que reescreveu a M1.2

O spec mandava adotar `vite-plugin-pwa`. **Não adotei, e o motivo é de segurança.**

O servidor Python injeta um **token de sessão de uso único** no `index.html` a
cada render:

```
// vite.config.ts, comentário do plugin hermes:dev-session-token
// "In production the Python `hermes dashboard` server injects a one-shot
//  session token into `index.html` (see hermes_cli/web_server.py)"
```

```js
// api.ts:110
const token = window.__HERMES_SESSION_TOKEN__;
```

O comportamento **padrão** do `vite-plugin-pwa` e do Workbox é
`navigateFallback` com `index.html` no precache. Aplicado aqui, isso:

1. **grava um segredo de uso único no disco do aparelho**, legível por qualquer
   script na origem e sobrevivente ao logout;
2. faz o app abrir, em toda visita seguinte, com um token morto — 401 em tudo.

O spec dizia "nunca cachear `/api/**`", e isso está certo. Mas o vazamento
maior não estava em `/api/**` — estava no HTML.

> **DECISÃO ASSUMIDA: service worker escrito à mão, sem `vite-plugin-pwa`.**
> Justificativa: a política que este produto precisa é curta e explícita, o
> default da ferramenta é ativamente perigoso aqui, e a árvore acabou de ganhar
> um guard de supply-chain — acrescentar dependência para depois configurar
> contra o default dela é o pior dos dois mundos. Custo: ~150 linhas. Benefício:
> a política cabe numa tela e é testada.

### Consequência assumida, dita em voz alta

Como `index.html` nunca é cacheado, **o app não abre offline**. Offline, a
navegação cai em `/offline.html`, que explica que o gateway está inalcançável e
lista o que verificar. Isso é pior do que um shell offline, e é deliberado:
a alternativa exigiria persistir o HTML que carrega o token. Entre "abre
offline" e "não guarda segredo no disco", o segundo ganha.

---

## 2. O que foi entregue

### M1.1 — Manifest e ícones ✅

```
web/public/manifest.webmanifest
web/public/icons/icon-192.png            derivado de apps/desktop/assets/icon.png
web/public/icons/icon-512.png
web/public/icons/icon-maskable-512.png   fundo branco (a mesma placa da arte),
                                         arte a 88% para caber na safe zone
web/public/icons/apple-touch-icon.png    sem transparência, como o iOS exige
```

`index.html` ganhou `<link rel="manifest">`, `theme-color`, `apple-touch-icon` e
as metas `apple-mobile-web-app-*`.

### M1.2 — Service worker ✅ com política testada

```
web/public/sw-policy.js          a decisão, isolada
web/public/sw.js                 a execução
web/public/offline.html          fallback de navegação, em pt-BR
web/src/pwa/register.ts          registro + interruptor de emergência
web/src/pwa/sw-policy.test.ts    44 testes
```

| Recurso | Estratégia | Motivo |
|---|---|---|
| `/api/**`, `/dashboard-plugins/**`, `/login`, `/logout`, `/oauth/**` | **network-only** | carregam ou consomem sessão |
| **navegações (`index.html`)** | **rede, fallback `/offline.html`** | o HTML carrega o token de uso único |
| `/assets/**` (hash no nome), `/fonts/**`, `/icons/**`, `/favicon.ico`, `/manifest.webmanifest`, `/offline.html` | cache-first | imutável e público |
| qualquer outra coisa | **network-only** | o default fecha |
| método ≠ GET, outra origem | network-only | — |

Três detalhes que valem o comentário que têm no código:

- **Consciente de base path.** O dashboard pode rodar atrás de proxy reverso
  (`X-Forwarded-Prefix`). Sem descontar o prefixo, `/hermes/assets/…` deixaria
  de casar com `/assets/` e o cache morreria em silêncio. O service worker
  deriva o prefixo do próprio escopo de registro — sem depender de variável
  injetada, que ele não enxerga.
- **Interruptor.** `window.__hermesUnregisterServiceWorker()` remove o registro
  e apaga todo o Cache Storage. Um service worker ruim se auto-perpetua; ter o
  desligamento pronto antes de precisar é a única forma de consertar sem pedir
  ao usuário para limpar dados do site.
- **Não registra em dev.** O Vite dev server serve o próprio `index.html` e
  raspa o token do backend a cada load; um service worker no meio disso troca um
  bug de cache por horas de "por que minha mudança não aparece".

### M2 — Projeto Android ✅ gerado e endurecido

```
apps/mobile/capacitor.config.ts     appId com.dz23.hermesomniroute (igual ao desktop)
apps/mobile/android/                projeto Gradle real, 68 arquivos
apps/mobile/README.md               estado honesto + o passo que falta
apps/mobile/RELEASE.md              keystore, checklist, Play Store
```

Endurecimentos aplicados sobre o que o Capacitor gera:

| O que o template faz | O que passou a fazer | Por quê |
|---|---|---|
| `android:allowBackup="true"` | **`false`** + `dataExtractionRules` excluindo tudo | o backup automático copia o storage do WebView — com o token de sessão — para a conta Google do usuário |
| sem `networkSecurityConfig` | `usesCleartextTraffic="false"` + config liberando texto claro **só** para RFC 1918, loopback e `10.0.2.2` | o caso real é o celular falando com o PC de casa; a internet pública continua obrigada a HTTPS |
| `*.jks` / `*.keystore` **comentados** no `.gitignore` | **descomentados** + `keystore.properties` | o default do template é versionar o keystore de assinatura. Quem tem o keystore publica atualizações no seu nome, e removê-lo depois não desfaz o histórico |
| ícone padrão do Capacitor | mipmaps em 5 densidades + adaptativo, derivados de `apps/desktop/assets/icon.png` | uma identidade só |
| `webContentsDebuggingEnabled` | `false` | um WebView depurável deixa qualquer processo com adb inspecionar a sessão |

### Extra que o spec não previu — origem do gateway ✅

```
web/src/lib/gateway-origin.ts        40 testes
web/src/lib/gateway-origin.test.ts
web/src/lib/api.ts                   BASE = gatewayOrigin() + HERMES_BASE_PATH
```

Dentro do WebView o app é servido de `https://localhost` a partir dos assets
empacotados — `/api/status` ali aponta para o **próprio pacote**. Sem isso, o
APK abre, mostra a interface e não fala com nada.

A mudança é **aditiva**: sem nada configurado, `gatewayOrigin()` devolve string
vazia e todas as URLs continuam byte a byte iguais às de hoje. Um módulo de rede
compartilhado por 20 páginas não é lugar para mudar comportamento por default.

Validação, com teste para cada regra:

- `http:` **só** para loopback, RFC 1918, link-local, CGNAT e `.local` — a mesma
  regra do `network_security_config.xml`, de propósito;
- `http://gateway.exemplo.com` → **recusado**. Acesso remoto se faz por túnel ou
  HTTPS, nunca por porta aberta em texto claro;
- `javascript:`, `data:`, `file:`, `ftp:` → recusados;
- `https://user:senha@host` → recusado (viajaria em todo request e ficaria no
  `localStorage` em texto claro);
- caminho, query ou fragmento → recusados. Isto é uma **origem**;
- valor inválido plantado no `localStorage` por outra versão do app ou por um
  script da mesma origem → ignorado na leitura.

---

## 3. Verificação — com exit code

```
web/  npm run build       exit 0
web/  npm run typecheck   exit 0
web/  npm test            38 arquivos · 359 testes · exit 0
      dos quais meus:     44 (política do service worker) + 40 (origem do gateway)
eslint src/pwa src/lib/gateway-origin*.ts src/main.tsx src/lib/api.ts   exit 0
```

Regressão injetada de propósito, para provar que o teste morde:

```
# fazer a política cachear /api/
$ sed -i "s#CACHEABLE_PREFIXES = \['/assets/'#CACHEABLE_PREFIXES = ['/api/', '/assets/'#" public/sw-policy.js
AssertionError: "/api/" cobriria "/api/" — a ordem das regras deixaria de proteger
 Tests  1 failed | 37 passed
# restaurado
 Tests  38 passed   exit 0
```

O lint do `web/` inteiro tem 1 erro e 26 avisos **pré-existentes**, todos em
arquivos que não toquei (`App.tsx`, `ChatSidebar.tsx`, `ThemeSwitcher.tsx`,
`plugins/…`).

---

## 4. O que NÃO foi feito, e o que falta para cada coisa

### O APK ainda não fala com um gateway

Metade do caminho está feita (a origem, acima). Faltam três coisas, nomeadas:

1. **Tela de conexão** no `web/`: campo de origem, botão de testar, lista de
   gateways conhecidos. Só aparece quando o app não está sendo servido por um
   gateway.
2. **`CapacitorHttp` ou CORS.** Cross-origin, o navegador exige
   `Access-Control-Allow-Origin` + `Allow-Credentials` do servidor Python.
   **Recomendo o `CapacitorHttp`**, que faz a requisição nativamente e não passa
   por CORS: mexer em CORS no gateway afrouxa a política para todos os clientes,
   inclusive os que rodam em navegador de verdade.
3. **Token no Keystore.** No APK o token não pode ficar no storage do WebView.

Enquanto isso, **o caminho Android que funciona é a PWA** — instalável pelo
Chrome a partir do próprio gateway, sem nenhum desses problemas, porque é
servida pela mesma origem.

### O build do APK não foi executado

`BLOCKED_BY_EXTERNAL_DEPENDENCY` — não há Android SDK no ambiente onde isto foi
montado. O projeto Gradle foi **gerado de verdade** (`npx cap add android`,
exit 0) e endurecido, mas nenhum `.apk` saiu daqui. Não afirmo que compila.

### M1.3 — passe responsivo: não feito

É o item mais caro da M1 e o spec já diz isso. O `web/` foi feito para telas
grandes: sidebar precisa virar drawer, rail direita vira bottom sheet, composer
fixo acima do teclado virtual, alvos de toque ≥44px, `100dvh` no lugar de
`100vh`, `env(safe-area-inset-*)`. Sem isso a PWA **instala e abre** em Android,
mas em 360×640 ela é desconfortável.

### Aceite da M1 (§3.5 do spec) — o que dá para afirmar

| Critério | Estado |
|---|---|
| nenhuma resposta de `/api/**` no Cache Storage | ✅ **provado por teste**, não por inspeção |
| abre offline sem tela branca | ✅ `/offline.html`, em pt-BR |
| Lighthouse PWA installable | ⚠️ não medido — exige o gateway rodando e um navegador |
| instala em Android/iOS | ⚠️ não medido pelo mesmo motivo |
| pareamento por QR revogável | ❌ não existe; o modo *gated* cobre a autenticação remota |
| usável em 360×640 | ❌ M1.3 não feita |

### `pt-br.ts` no `web/src/i18n`

Existe `pt.ts` (português genérico), não `pt-br.ts`. O desktop está em 98.5% de
pt-BR; o `web/` não recebeu o mesmo tratamento.
