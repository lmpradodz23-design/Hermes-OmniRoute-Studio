# HERMES OMNIROUTE — ARQUITETURA MULTIPLATAFORMA E MOBILE

Especificação de arquitetura. Ancorada em reconhecimento real do repositório em `c573d47`.

---

## 1. A DESCOBERTA QUE MUDA A ESTRATÉGIA

O Hermes **já é multi-cliente**. Não é preciso portar nada.

```text
apps/desktop/    Electron + React 19        cliente desktop      (Windows/macOS/Linux)
web/             React 19 + Vite 8 + TW4    cliente navegador    184 arquivos
ui-tui/          Ink                        cliente terminal     474 arquivos
gateway/         Python                     servidor + adaptadores de plataforma
apps/shared/     @hermes/shared             código comum entre clientes
website/         Docusaurus                 documentação         786 arquivos
```

O `web/` **não é um esqueleto**. É um cliente funcional:

```text
web/src/lib/api.ts            HTTP: /api/status /api/gateway /api/analytics /api/skills
                              /api/tools/toolsets /api/config /api/env /api/mcp
                              /api/model/options · /api/providers/oauth/<id>/start
web/src/lib/gatewayClient.ts  WebSocket via buildHermesWebSocketUrl (de @hermes/shared)
web/src/pages/                20 páginas
web/src/components/           29 componentes (ChatSidebar, ChatSessionList, Markdown,
                              AuthWidget, LanguageSwitcher, ModelInfoCard,
                              MemoryPressureBanner, HermesConsoleModal…)
web/src/i18n/                 21 arquivos
web/src/themes/               5 arquivos
web/src/plugins/              9 arquivos
dependências                  xterm (terminal real no browser), three + r3f, gsap,
                              motion, @observablehq/plot, qrcode, react-router
```

**Conclusão:** o caminho para Android e para "usar em diversas plataformas" não é construir um cliente novo. É **empacotar o cliente que já existe**.

---

## 2. DECISÃO DE ARQUITETURA

> **DECISÃO ASSUMIDA: mobile = cliente do gateway, não porte do desktop.**
> Justificativa: o gateway já expõe HTTP + WebSocket e já serve três clientes distintos. Portar Electron para Android é impossível (Electron não gera APK) e reescrever em React Native duplicaria 184 arquivos já testados. O `web/` já fala o protocolo.

```text
┌──────────────────────────────────────────────────────────────┐
│  GATEWAY HERMES  (Python)   HTTP /api/*  +  WebSocket        │
│  roda no PC do usuário, num servidor dele, ou em container   │
└───────┬──────────────┬──────────────┬───────────────┬────────┘
        │              │              │               │
   ┌────▼────┐   ┌─────▼─────┐  ┌─────▼─────┐   ┌─────▼──────┐
   │ Desktop │   │    Web    │  │    TUI    │   │  MOBILE    │
   │ Electron│   │ React/Vite│  │    Ink    │   │  ← NOVO    │
   │ Win/mac │   │ navegador │  │ terminal  │   │ PWA→APK    │
   │ /Linux  │   │           │  │           │   │            │
   └─────────┘   └───────────┘  └───────────┘   └────────────┘
                       └──────── mesmo build ────────┘
```

O cliente mobile **é o `web/`** com uma camada PWA e um passe responsivo. Um build, três destinos: navegador desktop, navegador móvel, e APK via wrapper.

---

## 3. FASE M1 — PWA (a maior parte do valor, o menor custo)

Transforma `web/` num app instalável em Android, iOS e desktop, sem toolchain novo.

### M1.1 Manifest
`web/public/manifest.webmanifest` — **não existe hoje** (verificado: nenhum manifest, service worker ou workbox no repositório).

```jsonc
{
  "name": "Hermes OmniRoute Studio",
  "short_name": "Hermes",
  "id": "/",
  "start_url": "/",
  "scope": "/",
  "display": "standalone",
  "display_override": ["window-controls-overlay", "standalone"],
  "orientation": "any",
  "background_color": "#0b0b0d",
  "theme_color": "#0b0b0d",
  "categories": ["developer", "productivity"],
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" },
    { "src": "/icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ],
  "shortcuts": [
    { "name": "Nova tarefa", "url": "/?new=1" },
    { "name": "Tarefas", "url": "/tasks" }
  ]
}
```

Ícones derivados de `apps/desktop/assets/icon.*` para manter uma identidade só.

### M1.2 Service worker
Adote `vite-plugin-pwa` (integra com o Vite 8 já em uso; não troca ferramenta).

**Política de cache — importante e não negociável:**

| Recurso | Estratégia | Motivo |
|---|---|---|
| shell (JS/CSS/fontes/ícones) | precache + `CacheFirst` | app abre offline |
| `/api/**` | **`NetworkOnly`** | **nunca cachear resposta de API** |
| WebSocket | não interceptar | streaming |
| qualquer resposta com credencial | **nunca cachear** | segurança |

> Um service worker que cacheia `/api/**` transforma dado de sessão em dado persistente no dispositivo. Isso vale como P0 no modelo de ameaça deste produto. `NetworkOnly` para `/api` é hardline.

### M1.3 Passe responsivo
O `web/` foi feito para telas grandes. Precisa de:
- breakpoints móveis reais para sidebar (vira drawer), rail direita (vira bottom sheet), composer (fixo no rodapé, acima do teclado virtual);
- alvos de toque ≥44px;
- `100dvh` em vez de `100vh` (barra de endereço móvel);
- `env(safe-area-inset-*)` para notch e barra de gestos;
- xterm em tela pequena: fonte menor, `fit` addon já está nas dependências.

### M1.4 Emparelhamento com o gateway
O gateway roda no PC; o celular precisa alcançá-lo. **`qrcode` já está nas dependências do `web/`** — provavelmente já existe fluxo de pareamento. Auditar antes de construir.

Regras:
- **loopback continua sendo o default.** Expor o gateway na LAN é opt-in explícito, com aviso claro.
- Token de sessão por dispositivo, revogável, com expiração; nunca em URL nem em query string.
- QR code carrega host + token de curta duração que é trocado por um token de dispositivo.
- Lista de dispositivos pareados nas configurações, com revogação individual.
- **Nunca** expor o gateway na internet pública sem autenticação — se o usuário quiser acesso remoto, documente túnel (Tailscale/WireGuard/SSH), não abertura de porta.

### M1.5 Aceite da M1
```text
Lighthouse PWA installable = pass
instala em Android (Chrome) e iOS (Safari, Adicionar à Tela de Início)
abre offline e mostra estado "sem conexão com o gateway" — não tela branca
nenhuma resposta de /api/** no Cache Storage (verificar em DevTools → Application)
pareamento por QR funciona e o token é revogável
sidebar/rail/composer usáveis em 360×640
```

---

## 4. FASE M2 — APK Android

> **DECISÃO ASSUMIDA: Capacitor, não React Native nem Tauri Mobile.**
> Justificativa: Capacitor embrulha o build web existente sem reescrever nada, tem ciclo de release maduro, e permite plugins nativos quando necessário. React Native exigiria reescrever 184 arquivos. Tauri Mobile ainda não tem a maturidade que um produto distribuído exige.

```text
apps/mobile/                       novo, mínimo
  capacitor.config.ts              webDir aponta para ../../web/dist
  android/                         projeto gerado
  package.json                     scripts: sync, open, build
```

Fluxo: `npm --prefix web run build` → `npx cap sync android` → build do APK/AAB.

**O que exige plugin nativo:**
- descoberta do gateway na LAN (mDNS) — opcional, o QR resolve sem isso;
- armazenamento seguro do token → **Android Keystore**, nunca `localStorage`;
- notificação quando uma aprovação fica pendente (liga com o badge "Ação necessária").

**Cuidados de release:** `applicationId` próprio (`com.dz23.hermesomniroute`, coerente com o desktop), keystore de assinatura **fora do repositório**, `networkSecurityConfig` permitindo cleartext **apenas** para a faixa local se o pareamento exigir, `android:usesCleartextTraffic="false"` como default.

### iOS
Mesmo Capacitor cobre iOS. Mas distribuição exige conta paga da Apple e revisão. **Não é bloqueante e não deve entrar no escopo agora** — a PWA já atende iOS via Safari.

---

## 5. FASE M3 — paridade desktop macOS/Linux

O Electron já tem alvos configurados (`dmg`, `AppImage`, `deb`, `rpm` no `package.json` do desktop; `entitlements.mac.*` estão inclusive no worktree sujo agora). O que falta é **prova**, não código:

- CI: `windows-primary` é obrigatório (F4 entregou isso); acrescentar lanes macOS e Linux que **empacotam de verdade**, não só rodam teste;
- macOS: notarização exige conta Apple Developer — se não houver, declare `BLOCKED_BY_EXTERNAL_DEPENDENCY` e documente o caminho "abrir mesmo assim";
- Linux: testar AppImage e `.deb` numa distro limpa em container;
- matriz de plataforma no R4 com resultado real por alvo.

---

## 6. O QUE **NÃO** FAZER

- **Não** portar Electron para Android. Não existe esse caminho.
- **Não** duplicar a lógica do `web/` num app nativo novo.
- **Não** expor o gateway na internet pública para "facilitar o mobile".
- **Não** cachear `/api/**` no service worker.
- **Não** guardar token em `localStorage` no APK — Keystore.
- **Não** criar um terceiro sistema de i18n. O `web/` já tem 21 arquivos de i18n; pt-BR precisa entrar lá também.

---

## 7. ORDEM E CUSTO RELATIVO

```text
M1.1 manifest + ícones          trivial
M1.2 service worker             pequeno — mas a política de cache é crítica
M1.3 passe responsivo           médio, é o grosso do trabalho
M1.4 pareamento/segurança       médio — auditar o fluxo de QR existente primeiro
M2   Capacitor + APK            pequeno depois da M1
M3   macOS/Linux CI + prova     médio, independente das demais
```

**M1 sozinha entrega "usar em diversas plataformas e sistemas operacionais".** M2 só acrescenta presença na Play Store.

---

## 8. PRIMEIRA TAREFA DE AUDITORIA ANTES DE CODIFICAR

Antes de escrever qualquer linha:

1. `web/` roda hoje? `npm --prefix web run build` e `npm --prefix web run check` — anexe exit code.
2. Qual o estado real do pareamento? Ler `web/src/lib/gatewayClient.ts` e localizar onde `qrcode` é usado.
3. O gateway autentica requisição de origem remota, ou só confia em loopback? Essa resposta define o tamanho da M1.4.
4. `apps/shared` já compartilha tokens de tema, ou só utilidades de rede? Define onde o design system mora (ver `HERMES_DESIGN_SYSTEM.md`).
5. pt-BR existe no `web/src/i18n`? Se não, entra no mesmo lote da tradução do desktop.
