# `apps/mobile` — APK Android do Hermes OmniRoute

Wrapper Capacitor. **Não há interface própria aqui**: a interface é `web/`,
empacotada. Ver `audit/HERMES_MULTIPLATFORM.md` §2 para o porquê.

```
apps/mobile/
  capacitor.config.ts     appId, webDir, política de esquema e cleartext
  android/                projeto Gradle gerado por `npx cap add android`
  RELEASE.md              assinatura, keystore, checklist de publicação
```

---

## Estado real, sem maquiagem

| Item | Estado |
|---|---|
| Projeto Android gerado e versionado | ✅ feito |
| `applicationId` `com.dz23.hermesomniroute` (mesmo do desktop) | ✅ feito |
| Ícones do launcher derivados de `apps/desktop/assets/icon.png` | ✅ feito |
| Backup para a nuvem desligado (o token de sessão não sai do aparelho) | ✅ feito |
| Cleartext só para faixas privadas | ✅ feito |
| `webContentsDebuggingEnabled=false` | ✅ feito |
| **Falar com um gateway remoto** | ⚠️ **falta um passo — leia abaixo** |
| Build do APK verificado | ❌ **não executado** — sem Android SDK no ambiente onde isto foi montado |

### O passo que falta, e por que ele não é opcional

Dentro do WebView, o app é servido de `https://localhost` a partir dos assets
empacotados. Uma chamada a `/api/status` resolve contra **o próprio pacote**,
onde não existe gateway nenhum. Sem tratar isso, o APK abre, mostra a interface
e não fala com nada.

Metade do caminho já está feita e testada:

- `web/src/lib/gateway-origin.ts` — o app aprende para onde falar. Origem
  validada, persistida, com HTTP em texto claro aceito **só** para a rede local
  (mesma regra do `network_security_config.xml`). 40 testes.
- `web/src/lib/api.ts` — `BASE` já usa essa origem. Com nada configurado, a
  string é vazia e **todas as URLs continuam idênticas às de hoje**.
- `buildHermesWebSocketUrl` (em `@hermes/shared`) já aceita `host` e `protocol`,
  então o WebSocket cross-origin não precisa de nada novo — WebSocket não passa
  por CORS.

O que ainda falta:

1. **Uma tela de conexão** no `web/`: campo para a origem do gateway, botão de
   testar, e a lista de gateways conhecidos. Só aparece quando o app não está
   sendo servido por um gateway (`gatewayOrigin()` disponível e nenhuma sessão).
2. **CORS, ou `CapacitorHttp`.** Cross-origin, o navegador exige que o servidor
   Python responda `Access-Control-Allow-Origin` + `Allow-Credentials` para
   `https://localhost`. A alternativa que não mexe no backend é ligar o plugin
   `CapacitorHttp`, que faz as requisições nativamente e não passa por CORS.
   **Recomendo o `CapacitorHttp`**: mexer em CORS no gateway afrouxa a política
   para todos os clientes, inclusive os que rodam em navegador de verdade.
3. **Token no Keystore.** No APK o token não pode ficar no storage do WebView.
   `@capacitor/preferences` com `EncryptedSharedPreferences`, ou um plugin de
   Keystore.

Enquanto esses três não existirem, **o caminho Android que funciona é a PWA** —
que já está pronta, é instalável pelo Chrome a partir do próprio gateway, e não
tem nenhum desses problemas porque é servida pela mesma origem. Ver
`audit/HERMES_MULTIPLATFORM.md` §3.

---

## Comandos

```bash
# 1. instala as dependências do wrapper
npm --prefix apps/mobile install

# 2. constrói o web/ e copia para o projeto Android
npm --prefix apps/mobile run sync

# 3. abre no Android Studio
npm --prefix apps/mobile run open

# APK de debug, sem assinatura de release
npm --prefix apps/mobile run apk:debug

# AAB de release (exige o keystore — ver RELEASE.md)
npm --prefix apps/mobile run aab:release
```

`sync` roda `npm --prefix ../../web run build` antes de copiar. O `webDir` do
Capacitor aponta para `hermes_cli/web_dist`, que é **o mesmo diretório** que o
servidor Python serve: um build, dois destinos, sem uma segunda árvore para
divergir.

## iOS

O mesmo Capacitor cobre iOS, mas distribuir exige conta paga da Apple e revisão.
Não está no escopo, e não bloqueia nada: a PWA já atende iOS pelo Safari
("Adicionar à Tela de Início").
