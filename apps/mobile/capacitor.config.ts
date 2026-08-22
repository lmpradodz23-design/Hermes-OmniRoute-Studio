import type { CapacitorConfig } from '@capacitor/cli'

/**
 * WRAPPER CAPACITOR — o APK é o cliente `web/` empacotado, não um app novo.
 *
 * Ver `audit/HERMES_MULTIPLATFORM.md` §2: o Hermes já é multi-cliente e o
 * gateway já expõe HTTP + WebSocket para três clientes. Portar o Electron para
 * Android não existe como caminho, e reescrever em React Native duplicaria 164
 * arquivos que já funcionam. O `web/` já fala o protocolo; aqui ele só ganha
 * um invólucro.
 *
 * ── O QUE ESTE ARQUIVO DECIDE, E POR QUÊ ────────────────────────────────────
 *
 * `androidScheme: 'https'`
 *   O WebView serve o conteúdo empacotado por `https://localhost`, não por
 *   `file://`. Duas razões, as duas obrigatórias: um contexto `file://` não é
 *   "secure context", então `navigator.serviceWorker` e `crypto.subtle`
 *   simplesmente não existem — e o `web/` depende dos dois. E a mesma origem
 *   estável é o que permite `localStorage`/IndexedDB persistirem entre
 *   atualizações do app.
 *
 * `cleartext: false`
 *   Sem HTTP em texto claro, como default. O caso do usuário que aponta o
 *   celular para `http://192.168.x.x:9119` é real, e é justamente por isso que
 *   ele precisa ser uma escolha consciente: ver `android/RELEASE.md` sobre o
 *   `network_security_config.xml` que libera cleartext **apenas** para faixas
 *   privadas. Ligar `cleartext: true` aqui liberaria a internet inteira.
 *
 * `webContentsDebuggingEnabled: false`
 *   Um WebView depurável deixa qualquer processo com acesso adb inspecionar a
 *   sessão do usuário. Fica desligado em release; ligue à mão para depurar.
 *
 * O que NÃO está aqui de propósito: `server.url`. Apontar o app para um
 * servidor remoto transformaria o APK numa casca que carrega código de rede —
 * e aí o binário assinado deixaria de corresponder ao que roda no aparelho.
 * O gateway é alcançado pelas chamadas `/api` do próprio app, não trocando a
 * origem do WebView.
 */
const config: CapacitorConfig = {
  appId: 'com.dz23.hermesomniroute',
  appName: 'Hermes OmniRoute',
  // O build do `web/` sai em `hermes_cli/web_dist` (é de lá que o servidor
  // Python serve o dashboard). O APK empacota exatamente o mesmo diretório:
  // um build, dois destinos, sem uma segunda árvore para divergir.
  webDir: '../../hermes_cli/web_dist',
  android: {
    allowMixedContent: false,
    webContentsDebuggingEnabled: false
  },
  server: {
    androidScheme: 'https',
    cleartext: false
  }
}

export default config
