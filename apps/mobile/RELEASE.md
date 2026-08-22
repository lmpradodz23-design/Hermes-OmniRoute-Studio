# Publicação do APK — o que precisa existir antes

## 1. Keystore — fora do repositório, sempre

Perder o keystore significa **nunca mais poder atualizar o app publicado**. A
Play Store identifica o app pela assinatura; sem a chave original, a única saída
é publicar um app novo, com outro `applicationId`, e pedir a todos os usuários
que reinstalem.

```bash
keytool -genkeypair -v \
  -keystore hermes-omniroute-release.jks \
  -alias hermes-omniroute \
  -keyalg RSA -keysize 4096 -validity 10000
```

Guarde o `.jks` e as senhas num gerenciador de segredos. **Não** no repositório,
**não** em variável de ambiente commitada, **não** num `gradle.properties`
versionado.

`android/.gitignore` já ignora `*.jks`, `*.keystore` e `keystore.properties` —
confira antes do primeiro commit, porque um keystore que entra no histórico do
git está comprometido mesmo depois de removido.

O caminho seguro para o Gradle achar a chave:

```properties
# android/keystore.properties  — NÃO versionado
storeFile=/caminho/absoluto/fora/do/repo/hermes-omniroute-release.jks
storePassword=...
keyAlias=hermes-omniroute
keyPassword=...
```

## 2. Antes de gerar o release, confira

- [ ] `android:debuggable` ausente do manifest de release (o Gradle cuida disso,
      mas confira o manifest final em `app/build/outputs/logs/`)
- [ ] `webContentsDebuggingEnabled: false` no `capacitor.config.ts`
- [ ] `android:allowBackup="false"` e `dataExtractionRules` excluindo tudo — um
      backup automático levaria o token de sessão para a conta Google do usuário
- [ ] `usesCleartextTraffic="false"` e `network_security_config.xml` liberando
      texto claro **só** para faixas privadas
- [ ] versão do web bundle é a mesma do commit da tag
      (`npm --prefix apps/mobile run sync` roda o build do zero)
- [ ] `versionCode` incrementado — a Play Store recusa o mesmo duas vezes

## 3. `versionCode` e `versionName`

Ficam em `android/app/build.gradle`. Amarre-os a uma tag do git em vez de editar
à mão: um `versionCode` repetido é rejeitado no upload, e um `versionName` que
não bate com nenhum commit torna impossível reproduzir o binário —
exatamente o problema que `audit/OPENSOURCE_PRE_PUBLICACAO.md` §P1-5 descreve
para o instalador Windows.

## 4. Play Store

- **Data safety**: o app não coleta dados. Ele fala com um gateway que o
  **próprio usuário** hospeda. Declarar isso com precisão evita rejeição.
- **Permissões**: só `INTERNET`. Qualquer permissão nova exige justificativa no
  formulário — não adicione nenhuma sem necessidade demonstrada.
- **Cleartext em rede local**: se a revisão perguntar, a resposta é o
  `network_security_config.xml`, que limita texto claro a RFC 1918 + loopback.

## 5. Sem conta de desenvolvedor

Um APK assinado fora da Play Store instala por "fontes desconhecidas". Documente
isso honestamente, com o SHA-256 do APK publicado ao lado do download, do mesmo
jeito que o instalador Windows faz. Não finja que o aviso do Android não aparece.
