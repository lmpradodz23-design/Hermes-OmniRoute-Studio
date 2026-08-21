# HERMES OMNIROUTE — FINDINGS

Convenção: **FACT** = verificado no código ou por execução, com arquivo:linha ou output. **HYPOTHESIS** = inferência plausível não executada. `ORIGEM: upstream` = defeito herdado do Hermes original, não introduzido pelo OmniRoute (ainda assim precisa de decisão).

## Tabela priorizada

| ID | Sev | Componente | Finding | Causa raiz | Evidência | Correção |
|---|---|---|---|---|---|---|
| HERMES-001 | P0 | Guardrails | O plugin `dz23-guardrail` nunca carrega; os 7 hooks ficam inertes | `plugin.yaml` sem `kind:` → `standalone`; bundled standalone é opt-in via `plugins.enabled` e nada o habilita | `hermes_cli/plugins.py:1063`, `:4001-4017`, `:591-618`; `config_migrations.py:319-322` | Declarar `kind: backend` **e** habilitar explicitamente no primeiro run; falhar alto se ausente |
| HERMES-002 | P0 | MCP bridge | Execução de código arbitrário via `OMNIROUTE_PACKAGE_ROOT` | Raiz do pacote vem de env sem validação; `import()` de `.mjs`/`.ts` daquele diretório via loader tsx | `integrations/omniroute-mcp-bridge.mjs:13-46` | Allowlist de raízes, resolução canônica, checagem de versão/integridade, ignorar env não confiável |
| HERMES-003 | P0 | MCP scopes | `OMNIROUTE_MCP_ENFORCE_SCOPES=true` não restringe nada — os escopos são auto-concedidos | O servidor usa `MCP_ALLOWED_SCOPES` (mesma env que o cliente define) como escopos do chamador | `server.ts:97-98`, `:225-230`; `main.ts:14432-14444` | Escopos vindos de identidade autenticada, não de env do próprio cliente; conjunto mínimo por default |
| HERMES-004 | P0 | Electron IPC | `openExternal('file://…')` → `shell.openPath` sem confinamento = execução local a partir do renderer | Ramo `file:` tratado antes do allowlist de esquemas e sem `rejectSensitiveFilePath` | `main.ts:1555-1581`, `:14343`; `hardening.ts:360-399` · ORIGEM: upstream | Confinar a raízes permitidas, bloquear executáveis, exigir confirmação |
| HERMES-005 | P1 | Guardrails | Denylist destrutivo não cobre Windows | 3 regexes POSIX-céntricos | **Execução provada** — ver §HERMES-005 | Denylist por plataforma + parser real de comando |
| HERMES-006 | P1 | Guardrails | Gate de verificação satisfeito por `echo` e por teste que falhou | `_is_success` aceita string sem "error"; `_VERIFY_PATTERN` casa texto, não execução | **Execução provada** | Exigir exit code real do runtime, não heurística de texto |
| HERMES-007 | P1 | Guardrails | Caminho relativo ignora o gate de fora-do-workspace | `_outside_workspace` retorna `False` para path não absoluto | **Execução provada** | Resolver contra a raiz da sessão antes de decidir |
| HERMES-008 | P1 | Guardrails | `Path.cwd()` e `/workspace` como raízes confiáveis | Raiz de confiança derivada do cwd do processo | **Execução provada** | Usar `agent/runtime_cwd.resolve_agent_cwd()`; remover `/workspace` fixo |
| HERMES-009 | P1 | Boot | Erro de I/O nos `installBundled*` aborta o `whenReady` e o app não abre | 4 chamadas sem try/catch dentro do callback | `main.ts:15079-15110` | try/catch por bundle + telemetria visível ao usuário |
| HERMES-010 | P1 | Isolamento | O Studio escreve dentro do runtime do Hermes original | `ACTIVE_HERMES_ROOT` é o runtime compartilhado | `main.ts:15085-15098`, `:732`; `docs/hermes-omniroute-studio.md:38` | Namespace próprio para plugins/integrations do Studio |
| HERMES-011 | P1 | Aprovações | `npm install` / `pip install` executam sem gate algum | Nenhum padrão em `DANGEROUS_PATTERNS`; retorno antecipado antes do smart | `tools/approval.py:774-1085`, `:4620-4623`, `:3356-3358` | Padrão dedicado + OSV para todo install, não só MCP |
| HERMES-012 | P1 | SSH | Caminho real do Windows sem cobertura; testes forçados a `mux:true` | Testes adaptados ao invés de cobrir o default da plataforma | `ssh-connection.test.ts` (9 sites) | Parametrizar a suíte por `mux` true/false |
| HERMES-013 | P1 | Electron | Nenhuma CSP + `webviewTag:true` + sem `will-attach-webview` | Política nunca definida | `session-windows.ts:46-57`; ausência de `onHeadersReceived` · ORIGEM: upstream | CSP restritiva + `will-attach-webview` que zera atributos perigosos |
| HERMES-014 | P1 | Plugins | `pre_tool_call` é fail-open duas vezes | `except Exception` no dispatcher e no invoke | `agent/tool_executor.py:643-644`; `hermes_cli/plugins.py:5140-5146` | Fail-closed para plugins marcados security-critical |
| HERMES-015 | P1 | Plugins | Falha de carga de plugin de segurança é só um warning | Sem distinção entre plugin opcional e crítico | `hermes_cli/plugins.py:4877-4894` | Flag `security_critical` no manifesto → aborta o start |
| HERMES-016 | P1 | Roteamento | Endpoint OmniRoute local sem autenticação nem verificação de identidade | `http://127.0.0.1:20128/v1` fixo, sem chave, validação só por alcançabilidade | `omniroute-preset.ts:2`; `custom-endpoints-settings.tsx:170-180` | Token local obrigatório + verificação de identidade do servidor |
| HERMES-017 | P2 | pt-BR | Catálogo pt-BR cobre ~15% das chaves | Tradução parcial com fallback silencioso para inglês | Medição: ≈380 de ≈2452 | Completar o catálogo + teste de cobertura mínima |
| HERMES-018 | P2 | UI/Segurança | Indicador "Acesso do agente ativo" é estático e some abaixo de `lg` | Texto fixo sem binding; classe `hidden … lg:flex` | `preview-browser-bar.tsx:188-196`; `en.ts` | Refletir estado real; visível em toda largura |
| HERMES-019 | P2 | Doc×Código | Doc promete backups timestamped; o código não faz backup | `copyFileSync` direto | `bundled-product-studio.ts:47-56` vs `docs/…:38` | Implementar backup ou remover a promessa |
| HERMES-020 | P2 | Segredos | `_redact` falha aberto — relatório sai sem redação se o import falhar | `except Exception: return value` | `plugins/dz23-guardrail/__init__.py:158-165` | Fail-closed: sem redator, não escreve o relatório |
| HERMES-021 | P2 | Config | O preset sobrescreve config do usuário; o teste "preserva" verifica uma chave que ele não toca | Merge raso com valores fixos | `omniroute-preset.ts:52-105`; `omniroute-preset.test.ts:63-72` | Só preencher ausentes; teste por chave sobrescrita |
| HERMES-022 | P2 | Testes | 8 assertions viram no-op no Windows e o teste reporta PASS | `if (process.platform !== 'win32')` dentro do corpo | 8 sites listados em §HERMES-022 | Trocar por `skipIf` (reporta skip) + teste equivalente Windows |
| HERMES-023 | P2 | Testes | Testes que só verificam frases em Markdown | `assert "<frase>" in body` | `tests/skills/test_product_studio_skill.py` (todos) | Testar comportamento; manter no máximo 1 smoke de schema |
| HERMES-024 | P2 | Guardrails | Falsos positivos bloqueiam documentação e SQL legítimos | Regex aplicada ao JSON inteiro dos args | **Execução provada** | Casar só no texto executável, nunca no conteúdo |
| HERMES-025 | P2 | Goal | CLI e gateway divergem; mensagem afirma pausa mesmo se `pause` falhar | Lógica duplicada; `mgr.pause(...) or state` | `slash_commands.py:2859-2866`; `cli_commands_mixin.py:2994-3009` | Extrair função única; erro real se a pausa falhar |
| HERMES-026 | P2 | Aprovações | `rule_key` do plugin vira auto-aprovação permanente por diretório-pai | `rule_key` sem validação vira `pattern_key` no allowlist | `tools/approval.py:3841-3856`, `:3684-3687` | Namespacing forçado + granularidade máxima por arquivo |
| HERMES-027 | P2 | Caveman | Parse de status frágil; `set` propaga exceção crua | `lastIndexOf('\n{')` + `JSON.parse` sem guarda | `omniroute-compression.ts:47-52` | Protocolo com delimitador explícito + erro tipado |
| HERMES-028 | P2 | Verificação | `pre_verify` é nudge com teto 3, não gate | Contrato do runtime | `agent/conversation_loop.py:8195-8236`; `verify_hooks.py:21` | Modo estrito opcional que bloqueia o finish |
| HERMES-029 | P2 | Electron | `fetchLinkTitle` monta argv de `curl` sem `--` e sem allowlist de esquema | URL crua como último argumento | `main.ts:5205-5208`, `:5153` · ORIGEM: upstream | `--` + allowlist http/https |
| HERMES-030 | P2 | Testes | Só 11 dos 12 testes pulados são identificáveis estaticamente | Contagem não publicada | §HERMES-030 | Publicar a lista nomeada de skips no relatório da suíte |
| HERMES-031 | P2 | Relatório | `cost_usd` nunca chega ao hook; custo sempre $0 | Contrato do hook não inclui o campo | `__init__.py:389` vs `conversation_loop.py:6699-6726` | Adicionar `cost_usd` ao payload ou remover do relatório |
| HERMES-032 | P2 | MCP | 106 ferramentas enumeradas, 107 anunciadas | Número não derivado da fonte | §HERMES-032 | Gerar o número em build a partir de `countUniqueMcpTools` |
| HERMES-033 | P2 | Segredos | Proteção de `connection.json` não verificada no Windows | 7 testes POSIX pulados; sem equivalente Windows | `hardening.test.ts:30` | Teste de ACL Windows (`icacls`) |
| HERMES-034 | P2 | Update | `codesign --verify` falha aberto e re-assina ad-hoc; branch escolhida pelo renderer | Fluxo de reparo invertido | `main.ts:3010-3019`, `:14627` · ORIGEM: upstream | Abortar em verificação falha; branch fora do controle do renderer |
| HERMES-035 | P2 | Cron/Health | URL duplicada e métricas de log grosseiras | Literal repetido; regex conta por ocorrência | `omniroute-daily-health.py:13,31-35` | Constante única compartilhada + parse por nível real |
| HERMES-036 | P3 | Higiene | Reformatação Prettier misturada a mudanças de comportamento | Sem commit separado de formatação | `stage-native-deps.test.mjs`, `test-desktop.mjs` | Separar em dois commits |
| HERMES-037 | P3 | Path | `path.win32/posix.join` é no-op em produção; mudança feita para o teste | Teste dirigindo o código | `windows-hermes-path.ts:137,162` | Injetar o módulo `path` como dependência |
| HERMES-038 | P3 | Build | `normalizeWindowsVersion` engole parte inválida e não faz clamp em 65535 | `parseInt(...)||0` | `set-exe-identity.mjs:45-56` | Validar e falhar explicitamente |
| HERMES-039 | P3 | Plugin | `plugin.yaml` duplica `provides_hooks` e `hooks` | Duplicação | `plugins/dz23-guardrail/plugin.yaml:5-20` | Manter só a chave que o loader lê |
| HERMES-040 | P3 | i18n | Alias `portugues` sem acento não existe | Lista incompleta | `languages.ts:88-94` | Normalizar removendo acentos |
| HERMES-041 | P3→**operacional urgente** | Git | 3.192 linhas existem só no índice, sem commit, em clone raso | Nenhum commit local | `git log` = 1 commit grafted | **Criar um commit ou bundle de proteção antes de qualquer trabalho** |

---

# Detalhamento

## FINDING HERMES-001
```text
SEVERITY: P0 — CRITICAL
COMPONENT: Guardrails / sistema de plugins
FILE: plugins/dz23-guardrail/plugin.yaml ; hermes_cli/plugins.py
LOCATION: plugin.yaml:1-20 ; plugins.py:1063, :3979-3998, :4001-4017, :591-618
```
**FACT.** `plugin.yaml` não declara `kind:`. O loader assume `kind = "standalone"` (`hermes_cli/plugins.py:1063`). O plugin vive em `<repo>/plugins/`, logo `source = "bundled"` (`:4095-4101`). Em `_discover_and_load_inner`, o auto-load de bundled é concedido **apenas** para `kind == "backend"` (`:3979-3982`) e `kind == "platform"` (`:3996-3998`). Todo o resto cai no ramo opt-in:

```python
# hermes_cli/plugins.py:4001-4017
is_enabled = (enabled is not None and (lookup_key in enabled or manifest.name in enabled))
if not is_enabled:
    loaded = LoadedPlugin(manifest=manifest, enabled=False)
    loaded.error = "not enabled in config (run `hermes plugins enable {}` to activate)".format(lookup_key)
    continue
```

`_get_enabled_plugins()` retorna `None` quando `plugins.enabled` não existe (`:591-618`), e não há chave `"plugins"` em `DEFAULT_CONFIG`. A migração 20→21 é explícita: *"Bundled plugins (shipped in the repo itself) are NOT grandfathered — they ship off for everyone"* (`config_migrations.py:319-322`).

`grep -rn "dz23-guardrail"` em todo o repositório retorna **apenas** três lugares: `apps/desktop/package.json:227-228` (empacotamento), `main.ts:15089-15093` (cópia de arquivos) e o próprio teste. **Nada adiciona o plugin a `plugins.enabled`.**

**ROOT_CAUSE.** O instalador copia os arquivos do plugin mas nunca o habilita, e o manifesto não usa o único `kind` que auto-carregaria.

**IMPACT.** Todo o discurso de segurança do produto é vazio por default: bloqueio de comandos destrutivos, aprovação para escrita fora do workspace, gate de evidência de verificação e relatório de tarefa redigido — nenhum deles roda. `docs/hermes-omniroute-studio.md:31-35` afirma os quatro como "safe defaults".

**REPRODUCTION.**
1. Instalar o Studio e abrir o app.
2. `hermes plugins list` → `dz23-guardrail` aparece com `enabled=False` e erro `not enabled in config`.
3. Pedir ao agente `rm -rf /tmp/teste` num workspace: nenhuma mensagem "DZ23 Guardrail blocked".

**EVIDENCE.** Cadeia de código acima. Note que `tests/plugins/test_dz23_guardrail_plugin.py:7-8` carrega o módulo por `importlib.util.spec_from_file_location`, **contornando o loader inteiro** — é por isso que o teste passa enquanto a produção fica sem guardrail.

**RECOMMENDED_FIX.**
1. `kind: backend` no `plugin.yaml`, ou habilitação explícita gravada no `config.yaml` no primeiro run do Studio.
2. Adicionar `security_critical: true` ao manifesto e fazer o runtime **abortar o start** se um plugin assim não carregar (relaciona-se a HERMES-015).
3. Expor o estado do guardrail na UI (Configurações → Segurança): carregado/não carregado, com o motivo.

**REGRESSION_TEST.** Teste de integração que sobe o `PluginManager` real (não `importlib`) com o `config.yaml` que o instalador produz e assere que `pre_tool_call` do `dz23-guardrail` está registrado e é invocado numa chamada de ferramenta.

**DEPENDENCIES.** Bloqueia a validação de HERMES-005/006/007/008/024 em produção.

---

## FINDING HERMES-002
```text
SEVERITY: P0 — CRITICAL
COMPONENT: OmniRoute MCP bridge
FILE: integrations/omniroute-mcp-bridge.mjs
LOCATION: :13-46
```
**FACT.**
```js
function candidateRoots() {
  const roots = [process.env.OMNIROUTE_PACKAGE_ROOT]        // :14 — env, sem validação
  if (process.platform === 'win32') {
    if (process.env.APPDATA) roots.push(path.join(process.env.APPDATA, 'npm', 'node_modules', 'omniroute'))
  } ...
}
const root = candidateRoots().find(c => fs.existsSync(path.join(c, 'open-sse', 'mcp-server', 'server.ts')))
const aliasResolver = await import(pathToFileURL(path.join(root, 'bin', 'aliasResolver.mjs')).href)   // :38
await aliasResolver.registerAliasResolver(root)                                                       // :39
const tsxLoaderUrl = pathToFileURL(path.join(root, 'node_modules', 'tsx', 'dist', 'loader.mjs')).href  // :41
await import(tsxLoaderUrl)                                                                             // :42
const server = await import(pathToFileURL(path.join(root, 'open-sse','mcp-server','server.ts')).href)  // :61
```
Três `import()` dinâmicos de código executável a partir de um diretório escolhido em runtime. Nenhuma verificação de versão, hash, assinatura ou allowlist de caminho.

`main.ts:14421` passa `env: { ...process.env, NO_COLOR: '1' }` ao `execFile` do runner de compressão — ou seja, `OMNIROUTE_PACKAGE_ROOT` do ambiente do usuário **é herdado**.

**ROOT_CAUSE.** Descoberta de código executável controlada por variável de ambiente e por um diretório gravável pelo usuário (`%APPDATA%\npm\node_modules`), sem verificação de integridade.

**IMPACT.** Quem controlar `OMNIROUTE_PACKAGE_ROOT` — ou conseguir gravar em `%APPDATA%\npm\node_modules\omniroute` — executa Node arbitrário com os privilégios do usuário toda vez que o Hermes iniciar o servidor MCP ou o usuário mexer no switch do Caveman. Não é elevação de privilégio, mas é **persistência silenciosa com execução automática** e um alvo óbvio para um agente induzido por prompt injection.

**REPRODUCTION (não executada — HYPOTHESIS de exploração, FACT de código).**
1. Criar `C:\tmp\fake\open-sse\mcp-server\server.ts`, `C:\tmp\fake\bin\aliasResolver.mjs` e `C:\tmp\fake\node_modules\tsx\dist\loader.mjs`.
2. `setx OMNIROUTE_PACKAGE_ROOT C:\tmp\fake`.
3. Abrir o Studio → Configurações → alternar Caveman. O `aliasResolver.mjs` plantado executa.

**RECOMMENDED_FIX.**
1. Ignorar `OMNIROUTE_PACKAGE_ROOT` em build empacotado, ou aceitá-lo apenas se resolver para um caminho dentro de uma allowlist gravada na instalação.
2. Resolver o caminho canonicamente (`fs.realpathSync`) e rejeitar junctions/symlinks que escapem da raiz esperada.
3. Verificar `package.json` do pacote: nome `omniroute` e faixa de versão suportada; recusar fora da faixa com erro claro.
4. Preferir consumir o MCP do OmniRoute pelo transporte HTTP autenticado que o próprio pacote expõe (`httpTransport.ts`), eliminando o `import()` de TS em runtime.
5. Não usar `tsx` como loader em produção — consumir `dist/` compilado.

**REGRESSION_TEST.** Teste que aponta `OMNIROUTE_PACKAGE_ROOT` para um diretório temporário com estrutura válida e assere que a bridge **recusa** com erro de allowlist e não importa nada dele.

**DEPENDENCIES.** Relaciona-se a HERMES-003 (o que a bridge expõe depois de carregada).

---

## FINDING HERMES-003
```text
SEVERITY: P0 — CRITICAL
COMPONENT: MCP scope enforcement
FILE: <omniroute>/open-sse/mcp-server/server.ts ; scopeEnforcement.ts ; apps/desktop/electron/main.ts
LOCATION: server.ts:97-98, :219-230 ; scopeEnforcement.ts:71-98 ; main.ts:14432-14444
```
**FACT.**
```ts
// server.ts:97-98
const MCP_ENFORCE_SCOPES = process.env.OMNIROUTE_MCP_ENFORCE_SCOPES === "true";
const MCP_ALLOWED_SCOPES = new Set( /* de process.env.OMNIROUTE_MCP_SCOPES */ );

// server.ts:225 — os escopos do CHAMADOR caem de volta na MESMA lista
const scopeContext = resolveCallerScopeContext(extra, Array.from(MCP_ALLOWED_SCOPES));
```
E o Hermes, ao configurar o servidor, entrega exatamente essas duas variáveis:
```ts
// main.ts:14432-14444
env: {
  OMNIROUTE_MCP_ENFORCE_SCOPES: 'true',
  OMNIROUTE_MCP_SCOPES: 'execute:completions,execute:search,execute:skills,pricing:write,read:cache,
    read:catalog,read:combos,read:compression,read:gamification,read:health,read:local-corpus,read:memory,
    read:models,read:notion,read:obsidian,read:plugins,read:proxies,read:quota,read:skills,read:tools,
    read:usage,write:budget,write:cache,write:combos,write:compression,write:gamification,write:memory,
    write:notion,write:obsidian,write:plugins,write:resilience,write:skills'
}
```
São 32 escopos que cobrem a totalidade das categorias de ferramenta. Como o processo é lançado por stdio pelo próprio Hermes e não há `authInfo` de um IDP, `resolveCallerScopeContext` retorna `source: "env"` com o conjunto completo.

**ROOT_CAUSE.** O sujeito que é autorizado e o sujeito que concede a autorização são o mesmo processo. Enforcement de escopo só tem sentido quando os escopos vêm de uma identidade que o chamador não controla.

**IMPACT.** `OMNIROUTE_MCP_ENFORCE_SCOPES=true` transmite ao usuário e ao revisor que existe um modelo de permissão. Não existe. Em particular `write:plugins` libera `plugin_install`, `plugin_activate`, `plugin_configure` e `plugin_uninstall` — instalação e ativação de plugins é **superfície de execução de código**, concedida por default. `write:memory` libera envenenamento persistente de memória; `execute:search` libera `omniroute_web_fetch`, que traz conteúdo não confiável para dentro do agente.

**EVIDENCE.** Além do código acima, `server.ts:1374-1375` expõe `scopesEnforced` e `allowedScopes` num endpoint de status — o próprio servidor publica que a lista permitida é a lista completa.

**RECOMMENDED_FIX.**
1. Default mínimo: conceder apenas `read:health, read:models, read:combos, read:quota, execute:completions`. Tudo além disso é opt-in por consentimento explícito na UI, por ferramenta ou por categoria.
2. Remover `write:plugins`, `write:memory`, `write:obsidian`, `write:notion`, `execute:skills` do conjunto default.
3. Quando houver transporte HTTP autenticado, derivar escopos do token e ignorar a env.
4. Enquanto a env for a fonte, renomear a flag para algo honesto (`OMNIROUTE_MCP_DECLARED_SCOPES`) e **não** apresentá-la como enforcement.

**REGRESSION_TEST.** Teste que sobe o servidor MCP com escopo mínimo, chama `plugin_install` e assere `isError: true` com `missing_scopes`; e outro que assere que o conjunto default **não contém** `write:plugins`.

---

## FINDING HERMES-004
```text
SEVERITY: P0 — CRITICAL   (ORIGEM: upstream)
COMPONENT: Electron IPC / filesystem
FILE: apps/desktop/electron/main.ts ; fs-ipc.ts ; hardening.ts
LOCATION: main.ts:1555-1581, :14343 ; fs-ipc.ts:160-182 ; hardening.ts:360-399
```
**FACT.** `openExternalUrl` trata `file:` **antes** do allowlist de esquemas:
```js
if (parsed.protocol === 'file:') {
  const localPath = resolveRequestedPathForIpc(parsed.toString(), { purpose: 'Open external file' })
  void shell.openPath(localPath)          // main.ts:1565
  ...
  return true
}
if (!['http:', 'https:', 'mailto:'].includes(parsed.protocol)) return false   // main.ts:1584
```
`resolveRequestedPathForIpc` (`hardening.ts:360-399`) rejeita `\0` e device paths do Windows, expande `~` e resolve — **não confina a nenhuma raiz e não chama `rejectSensitiveFilePath`** (compare com `resolveReadableFileForIpc`, `hardening.ts:481`, que chama).

Em paralelo, `hermes:fs:writeText` (`fs-ipc.ts:160-182`) grava até 1 MB em **qualquer caminho** cujo diretório pai exista. O comentário em `fs-ipc.ts:156-159` afirma que o caminho "never escapes the allowed roots"; não há raiz implementada.

**ROOT_CAUSE.** Duas primitivas do preload — escrever arquivo em qualquer lugar e abrir arquivo com a associação do SO — sem confinamento, na mesma superfície.

**IMPACT.** Um renderer comprometido (e não há CSP — HERMES-013) encadeia:
```js
await hermesDesktop.writeTextFile('C:\\Users\\x\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\a.bat', 'payload')
await hermesDesktop.openExternal('file:///C:/Users/x/.../a.bat')
```
→ execução de código local. **HYPOTHESIS** quanto à exploração concreta (não executei); **FACT** quanto às duas primitivas e à ausência de confinamento.

**RECOMMENDED_FIX.**
1. `openExternalUrl`: confinar o ramo `file:` a raízes permitidas (workspace ativo, downloads do app), aplicar `rejectSensitiveFilePath`, e recusar extensões executáveis (`.exe .bat .cmd .ps1 .lnk .scr .msi .com .vbs .js .jar`) ou exigir confirmação explícita do usuário com o caminho visível.
2. `hermes:fs:*`: implementar de fato a allowlist de raízes que o comentário promete, e corrigir o comentário.
3. Validar origem do sender nos 165 canais IPC (rejeitar frames que não sejam o documento do app).

**REGRESSION_TEST.** Testes que asserem recusa para `file:///C:/Windows/System32/calc.exe`, para `~/.ssh/id_rsa` e para escrita fora das raízes permitidas.

---

## FINDING HERMES-005
```text
SEVERITY: P1 — HIGH
COMPONENT: Guardrails
FILE: plugins/dz23-guardrail/__init__.py
LOCATION: :16-25 (_DESTRUCTIVE_PATTERNS), :296-305 (on_pre_tool_call)
```
**FACT — provado por execução.** Carreguei o módulo e chamei `on_pre_tool_call('terminal', {'command': ...})`:
```text
PASSOU    | del /s /q C:\Users\zodyp\Documents
PASSOU    | rd /s /q C:\projeto
PASSOU    | Remove-Item -Recurse -Force C:\Users\zodyp
PASSOU    | rm -r -f /tmp/x
PASSOU    | rm --recursive --force /tmp/x
PASSOU    | find . -delete
PASSOU    | git clean -fdx
PASSOU    | DROP DATABASE producao
PASSOU    | TRUNCATE TABLE users
PASSOU    | docker volume prune -f
PASSOU    | shutil.rmtree("C:/x")
BLOQUEADO | rm -rf /tmp/x
```
**ROOT_CAUSE.** Denylist de três regexes escrito para POSIX, num produto cujo alvo declarado é Windows.

**IMPACT.** `docs/hermes-omniroute-studio.md:31` — *"Destructive shell/database/container commands are blocked by a deterministic `pre_tool_call` hook"* — é falso na plataforma de release. Um agente induzido por prompt injection apaga a árvore de projetos do usuário com `del /s /q` sem tocar no guardrail.

**RECOMMENDED_FIX.** Substituir o denylist por: (a) parser real de comando (o Hermes já tem `_command_detection_variants` em `tools/approval.py:2224`, que lida com quoting e `$()`); (b) cobertura explícita de Windows (`del`, `rd`, `rmdir`, `Remove-Item`, `Format-Volume`, `Clear-Disk`, `takeown`, `icacls /reset`, `reg delete`, `vssadmin delete shadows`, `cipher /w`); (c) SQL (`DROP DATABASE`, `TRUNCATE`, `DELETE FROM` sem `WHERE`); (d) Git (`clean -fdx`, `reset --hard`, `push --force`); (e) contêiner (`volume prune`, `image prune -a`, `rm -f`). Preferir **allowlist do que é seguro** onde possível.

**REGRESSION_TEST.** Tabela parametrizada com os 12 comandos acima como casos que **devem** bloquear, mais casos negativos que **não** devem (ex.: `git clean -n`).

---

## FINDING HERMES-006
```text
SEVERITY: P1 — HIGH
COMPONENT: Guardrails / gate de verificação
FILE: plugins/dz23-guardrail/__init__.py
LOCATION: :26-33 (_VERIFY_PATTERN), :104-115 (_is_success), :330-341 (on_post_tool_call)
```
**FACT — provado por execução.**
```text
apos escrita, pre_verify: {'action':'continue','message':'Verification evidence is missing…'}
apos "npm test" que FALHOU (string '5 tests failed, 0 passed', status 'success'): None   ← gate satisfeito
apos "echo npm test" (saida 'npm test'): None                                            ← gate satisfeito
```
Causa no código:
```python
def _is_success(result, status):
    ...
    if isinstance(result, str):
        try: parsed = json.loads(result)
        except (TypeError, ValueError): return "error" not in result.lower()   # :110
```
Qualquer saída textual que não contenha a substring `error` é considerada sucesso. E `_VERIFY_PATTERN` casa a **string do comando**, não a execução — `echo npm test` casa.

**FACT adicional.** `pytest` sozinho **não** casa o padrão: a primeira alternativa exige um segundo token (`test|check|lint|typecheck|build|verify|e2e`) depois do runner, e `pytest` não o tem. O comando de verificação mais comum do ecossistema Python não satisfaz o gate, enquanto `echo npm test` satisfaz.

**IMPACT.** `docs/hermes-omniroute-studio.md:33` — *"A coding task cannot be marked verified without fresh command evidence"* — é falso. O gate é forjável com uma linha, e falha justamente contra o caso que deveria pegar: teste que rodou e falhou.

**RECOMMENDED_FIX.**
1. Derivar sucesso do **exit code real** entregue pelo runtime (`result["exit_code"]`), nunca de heurística textual. Se o runtime não fornecer exit code, tratar como **não verificado** (fail-closed), não como sucesso.
2. Casar o comando por **argv normalizado**, não por regex sobre a string, e excluir `echo`, `printf`, `cat`, `type` e afins.
3. Registrar, junto do flag, qual comando produziu a evidência e o exit code, e incluir isso no relatório de tarefa.
4. Adicionar `pytest`, `python -m pytest`, `uv run pytest`, `tox`, `nox` como runners de primeira classe.

**REGRESSION_TEST.** Casos: exit 1 com stdout sem "error" → **não** verifica; `echo npm test` → **não** verifica; `pytest` com exit 0 → verifica; resultado sem `exit_code` → **não** verifica.

---

## FINDING HERMES-007
```text
SEVERITY: P1 — HIGH
COMPONENT: Guardrails / escopo de workspace
FILE: plugins/dz23-guardrail/__init__.py
LOCATION: :88-101 (_outside_workspace)
```
**FACT — provado por execução** (com `HERMES_GUARDRAIL_WORKSPACE_ROOTS=/tmp/ws`):
```text
'../../../../home/user/.ssh/authorized_keys' -> None
'..\..\Windows\System32\drivers\etc\hosts'   -> None
'./../../etc/passwd'                          -> None
```
`None` significa "sem diretiva" → a escrita segue sem aprovação. Causa:
```python
def _outside_workspace(path: Path) -> bool:
    if not path.is_absolute():
        return False        # :90-91 — qualquer caminho relativo é considerado dentro
```
**IMPACT.** O gate de "escrita fora do workspace requer aprovação" é anulado por travessia relativa, que é a forma mais natural de um modelo escrever um caminho. `docs/hermes-omniroute-studio.md:32` afirma o gate como safe default.

**RECOMMENDED_FIX.** Resolver todo caminho contra a raiz da sessão (`(root / path).resolve()`) **antes** de decidir, e comparar por `os.path.commonpath` sobre caminhos reais (`realpath`) para também cobrir symlink/junction.

**REGRESSION_TEST.** Casos com `..`, `..\`, symlink apontando para fora, caminho UNC `\\server\share\x` e caminho com `~`.

---

## FINDING HERMES-008
```text
SEVERITY: P1 — HIGH
COMPONENT: Guardrails / raiz de confiança
FILE: plugins/dz23-guardrail/__init__.py
LOCATION: :56-70 (_workspace_roots)
```
**FACT — provado por execução.**
```text
cwd do processo = /
roots = (PosixPath('/'), PosixPath('/workspace'))
write em /etc/passwd                 -> None
write em /root/.ssh/authorized_keys  -> None
```
E, independentemente do cwd:
```text
cwd = /tmp | roots = (PosixPath('/tmp'), PosixPath('/workspace'))
write em /workspace/x -> None
```
Código:
```python
values.extend([str(Path.cwd()), "/workspace"])     # :62
```
**ROOT_CAUSE.** A raiz de confiança é derivada do diretório de trabalho do processo — que não é uma fronteira de segurança — e um caminho fixo `/workspace` é sempre confiável.

**FACT complementar** (do mapeamento do runtime): o processo do agente **nunca** chama `os.chdir` (as três ocorrências no repo estão em `hermes_cli/main.py:2957,3036` e `cli_commands_mixin.py:1340`). Logo `Path.cwd()` é o diretório de lançamento — do gateway, do serviço ou do Electron — e **não** o workspace lógico da sessão. Em modo gateway multi-sessão o guardrail compara contra a raiz errada em todas as sessões.

**IMPACT.** Se o backend for lançado da raiz de um drive, de `C:\` ou do diretório de instalação, o gate de workspace deixa de existir. Em gateway multi-sessão ele é simplesmente incorreto.

**RECOMMENDED_FIX.** Usar `agent/runtime_cwd.resolve_agent_cwd()` (`agent/runtime_cwd.py:60`), que respeita o contextvar `_SESSION_CWD` e `TERMINAL_CWD`. Remover `/workspace` fixo (ou torná-lo condicional a um marcador de container). Se nenhuma raiz de sessão puder ser resolvida, **fail-closed**: exigir aprovação para qualquer escrita absoluta.

**REGRESSION_TEST.** Teste que lança o processo com cwd `/` e assere que escrita em `/etc/passwd` exige aprovação; teste multi-sessão com dois workspaces distintos.

---

## FINDING HERMES-009
```text
SEVERITY: P1 — HIGH
COMPONENT: Boot do Electron
FILE: apps/desktop/electron/main.ts
LOCATION: :15079-15110
```
**FACT.** Dentro de `app.whenReady().then(() => { … })`:
```ts
if (IS_PACKAGED) {
  const productStudioResult = installBundledProductStudioSkill({...})
  const guardrailResult     = installBundledDz23Guardrail({...})
  const mcpBridgeResult     = installBundledOmniRouteMcpBridge({...})
  const healthScriptResult  = installBundledOmniRouteHealthScript({...})
  console.log(`[hermes-omniroute] product studio skill: ${productStudioResult}`)
  ...
}
const systemCa = installWindowsSystemCaTrust(tls)   // ← só roda se nada acima lançar
```
Nenhuma das quatro chamadas está em `try/catch`, e `installManagedBundle` executa `fs.mkdirSync`, `fs.copyFileSync` e `fs.writeFileSync` (`bundled-product-studio.ts:47-56`) — todas capazes de lançar `EACCES`, `EPERM`, `EBUSY`, `ENOSPC`.

**IMPACT.**
1. **Disponibilidade:** uma exceção aborta o restante do callback `whenReady` — CA trust, criação de janela, tudo. O app não abre e a exceção vira unhandled rejection. Antivírus segurando um handle em `plugins/dz23-guardrail/__init__.py` é suficiente.
2. **Silêncio:** os retornos `skipped-unmanaged` e `skipped-missing` só vão para `console.log`. Se o guardrail não for instalado, nada informa o usuário — o app roda "sem guardrail" com aparência normal.

**RECOMMENDED_FIX.** `try/catch` por bundle; agregar o resultado num estado consultável por IPC; exibir em Configurações → Segurança o estado de cada bundle gerenciado (instalado / atualizado / pulado-não-gerenciado / falhou + motivo); nunca deixar a instalação de bundle no caminho crítico da criação de janela.

**REGRESSION_TEST.** Teste que injeta um `fs` que lança em `copyFileSync` e assere que (a) o app continua o boot, (b) o estado reporta `failed` com o erro.

---

## FINDING HERMES-010
```text
SEVERITY: P1 — HIGH
COMPONENT: Isolamento Studio × Hermes original
FILE: apps/desktop/electron/main.ts ; docs/hermes-omniroute-studio.md
LOCATION: main.ts:15085-15098, :732 ; docs:38
```
**FACT.** `ACTIVE_HERMES_ROOT = path.join(HERMES_HOME, 'hermes-agent')` (`main.ts:732`) — o runtime compartilhado do Hermes. O Studio grava lá:
```ts
installBundledDz23Guardrail({ destinationRoot: path.join(ACTIVE_HERMES_ROOT, 'plugins', 'dz23-guardrail'), ... })
installBundledOmniRouteMcpBridge({ destinationPath: path.join(ACTIVE_HERMES_ROOT, 'integrations', 'omniroute-mcp-bridge.mjs'), ... })
```
E a própria documentação confirma o compartilhamento: *"The original `%LOCALAPPDATA%\hermes` runtime can be reused for compatibility"* (`docs:38`).

**IMPACT.** A separação lado-a-lado é real no nível de aplicação (appId, executável, protocolo, userData) e **falsa no nível de runtime**. Instalar o Studio injeta código Python executável e um bridge Node no runtime que o Hermes upstream também usa. Desinstalar o Studio não remove esses arquivos (o `.omniroute-managed.json` marca propriedade mas nada faz a limpeza). A premissa "Hermes original preservado" não se sustenta.

**RECOMMENDED_FIX.**
1. Namespace próprio: `HERMES_HOME/omniroute-studio/{plugins,integrations,scripts}` e adicioná-lo ao path de descoberta do backend em vez de escrever no runtime original.
2. Se o compartilhamento for uma decisão deliberada, documentá-la explicitamente como *modificação do runtime original* e implementar desinstalação que reverta.
3. Implementar os backups timestamped que a doc já promete (HERMES-019).

**REGRESSION_TEST.** Teste que assere que nenhum caminho de instalação escreve fora do namespace do Studio; teste de desinstalação que assere remoção completa dos arquivos gerenciados.

---

## FINDING HERMES-011
```text
SEVERITY: P1 — HIGH
COMPONENT: Aprovações / supply chain
FILE: tools/approval.py ; apps/desktop/src/app/settings/omniroute-preset.ts ; skills/.../nontechnical-intake.md
LOCATION: approval.py:774-1085, :4620-4623, :3356-3358 ; omniroute-preset.ts:76-88 ; intake:28
```
**FACT.** `DANGEROUS_PATTERNS` (`approval.py:774-1085`) não contém nenhum padrão para `npm`, `pnpm`, `yarn`, `bun`, `pip`, `uv`, `cargo install`, `gem install` ou `go install`. Consequência em `check_all_command_guards`:
```python
# approval.py:4620-4623 — ANTES do bloco smart
if not warnings:
    return {"approved": True, "message": None}
```
O comando nem chega ao aprovador LLM. E se chegasse, o system prompt manda aprovar:
```python
# approval.py:3356-3358
"- APPROVE if the command is clearly safe (benign script execution, "
"safe file operations, development tools, package installs, git operations)\n"
```
O único guard de malware existente (`tools/osv_check.py`) só é consultado para extensões MCP via `npx`/`uvx` (`tools/mcp_tool.py:3032`) e é fail-open em erro de rede.

O preset do Studio define `approvals.mode: 'smart'` com a política *"Auto-approve … dependency installation …"* (`omniroute-preset.ts:83`), e a skill instrui *"Install project dependencies automatically inside the active workspace"* (`nontechnical-intake.md:28`).

**IMPACT.** `npm install <pacote>` executa `postinstall` arbitrário. É o vetor clássico de typosquatting e supply-chain, e neste produto ele passa **sem nenhum gate**, para um público explicitamente descrito como não técnico. A `smart_policy` é inútil aqui porque o comando nunca chega ao LLM que a leria.

**RECOMMENDED_FIX.**
1. Padrão dedicado em `DANGEROUS_PATTERNS` para instaladores de pacote, com o nome do pacote extraído.
2. Consultar OSV para todo install, não só MCP; **fail-closed** quando a consulta falhar e o pacote for novo para o workspace.
3. `--ignore-scripts` por default para `npm/pnpm/yarn`, com opt-in explícito.
4. Distinguir "instalar dependência **já declarada** no lockfile do workspace" (auto-aprovável) de "adicionar dependência nova" (requer aprovação com o nome do pacote e o publisher visíveis).

**REGRESSION_TEST.** `npm install left-pad` sem lockfile → exige aprovação; `npm ci` com lockfile existente → auto-aprovado; pacote com advisory `MAL-*` → bloqueado.

---

## FINDING HERMES-012
```text
SEVERITY: P1 — HIGH
COMPONENT: SSH
FILE: apps/desktop/electron/ssh-connection.test.ts
LOCATION: :282, :314, :349-352, :378, :390, :413, :457, :471, :894, :905, :926 (mux:true) ; :804, :820 (return win32)
```
**FACT.** Onze construtores de `SshConnection` receberam `mux: true` no diff staged. `ssh-connection.ts` **não está no stage** — o código de produção não mudou. A única explicação consistente é que a suíte passou a rodar no Windows, onde o default de `mux` é diferente, e os testes foram ajustados para continuar exercitando o caminho multiplexado.

Consequência: as propriedades testadas — sondar liveness antes de abrir, exec-verify de master vivo, despejo de master travado, remoção do control socket, isolamento por escopo, `disown` quando `-O exit` falha — descrevem **um caminho que não é o que roda no Windows**. O caminho real (sem multiplexação) tem **zero cobertura**.

Além disso, `:804` e `:820` acrescentam `if (process.platform === 'win32') return` — dois testes, um deles sobre **recusa de control-dir que é symlink**, reportam PASS no Windows sem asserir nada.

**FACT agravante.** O único teste de ciclo de vida SSH real (`windows-remote-live.test.ts:28`) é `skipIf(!liveHost || !liveUser || !configuredHermes)` — pulado sempre que a trinca de env não está configurada. Ou seja: **nenhum teste do produto exercita SSH de verdade**.

**IMPACT.** SSH é a superfície mais crítica do produto (acesso a servidor remoto do usuário) e é a menos coberta na plataforma de release. Reconexão, host spoofing, fallback e limpeza de socket no caminho Windows são não verificados.

**RECOMMENDED_FIX.**
1. Parametrizar a suíte por `mux: [true, false]` e rodar ambos em todas as plataformas.
2. Substituir os `return` win32 por `test.skipIf` (para reportar skip honestamente) e escrever o equivalente Windows (junction em vez de symlink).
3. Tornar o teste live executável em CI com um container OpenSSH efêmero, em vez de depender de um rig manual.

**REGRESSION_TEST.** Ver acima; adicionar teste de que a verificação de host key nunca faz fallback silencioso para outro host.

---

## FINDING HERMES-013
```text
SEVERITY: P1 — HIGH   (ORIGEM: upstream)
COMPONENT: Electron / renderer
FILE: apps/desktop/electron/session-windows.ts ; main.ts ; apps/desktop/index.html
LOCATION: session-windows.ts:46-57 ; ausência de onHeadersReceived em main.ts
```
**FACT.** Base sólida: `contextIsolation: true`, `sandbox: true`, `nodeIntegration: false` em **todas** as 12 janelas; `setWindowOpenHandler` sempre `deny`; preload com API nominal sem passthrough de canal. Mas:
- **Nenhuma CSP.** `onHeadersReceived` não existe em `electron/`; `session.defaultSession` recebe download, permissão, headers e spellcheck — nenhum injeta CSP; `index.html` não tem meta CSP.
- **`webviewTag: true`** nas 7 janelas de chat/overlay (`session-windows.ts:50`).
- **`will-attach-webview` e `web-contents-created` não existem** em todo o repositório.
- `will-navigate` aceita `url.startsWith('file:')` em build empacotado (`main.ts:10965`) — qualquer arquivo local navega a janela principal, que carrega o preload completo.
- `setPermissionCheckHandler` retorna `true` para mídia **ignorando a origem** (`main.ts:6688-6694`).

**IMPACT.** Sem CSP, um XSS no renderer principal alcança os 165 canais IPC. Sem `will-attach-webview`, os atributos de `<webview>` vêm exclusivamente do DOM — um `<webview nodeintegration preload="file:///…">` injetado por script não é filtrado por nada no main. **HYPOTHESIS** quanto à exploração; **FACT** quanto às ausências.

**RECOMMENDED_FIX.**
1. CSP restritiva via `onHeadersReceived` para a origem do app: `default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'`.
2. `app.on('web-contents-created')` + `will-attach-webview` que force `nodeIntegration=false`, `contextIsolation=true`, remova `preload` não esperado e valide `src` contra allowlist.
3. `will-navigate`: comparar origem, não prefixo; confinar `file:` ao diretório `dist/` do app.
4. `will-redirect` com a mesma política.
5. Permissões por origem, não globais.

**REGRESSION_TEST.** Teste que assere o header CSP na resposta da origem do app; teste que assere que um `<webview>` com `nodeintegration` é neutralizado pelo handler.

---

## FINDING HERMES-014
```text
SEVERITY: P1 — HIGH
COMPONENT: Sistema de hooks
FILE: agent/tool_executor.py ; hermes_cli/plugins.py
LOCATION: tool_executor.py:624-651 (esp. :643-644) ; plugins.py:5104-5147 (esp. :5140-5146)
```
**FACT.** Dois níveis de fail-open:
```python
# agent/tool_executor.py:643-644
except Exception:
    return None          # ← "sem diretiva de bloqueio" → a ferramenta EXECUTA
```
```python
# hermes_cli/plugins.py:5140-5146 — cada callback num try/except que só faz logger.warning
```
**IMPACT.** Um hook `pre_tool_call` que lance qualquer exceção — inclusive por bug no próprio guardrail, por `ImportError` transitório ou por argumento inesperado — resulta em execução da ferramenta que ele deveria bloquear, com uma linha de warning em log. Para um hook de segurança, o default correto é o oposto.

**RECOMMENDED_FIX.** Introduzir `security_critical: true` no manifesto. Para plugins assim: exceção no hook → **bloqueia** a chamada com mensagem clara; falha de carga → aborta o start (HERMES-015). Registrar toda exceção de hook de segurança em audit log, não só em `logger.warning`.

**REGRESSION_TEST.** Hook que lança → ferramenta bloqueada; hook não-crítico que lança → comportamento atual preservado.

---

## FINDING HERMES-015
```text
SEVERITY: P1 — HIGH
COMPONENT: Carregamento de plugins
FILE: hermes_cli/plugins.py
LOCATION: :4877-4894, :4820-4822
```
**FACT.** Falha de carga captura `Exception` amplo, faz rollback correto dos registros parciais (bom design) e emite `logger.warning`. O stack trace só aparece com `HERMES_PLUGINS_DEBUG=1`. O app continua normalmente com `enabled=False`.

**IMPACT.** Para o `dz23-guardrail`, qualquer falha — por exemplo `from hermes_constants import get_hermes_home` (`__init__.py:151`) num layout inesperado — deixa o agente rodando **sem** bloqueio de comandos destrutivos e **sem** aprovação de escrita fora do workspace, invisivelmente.

**RECOMMENDED_FIX.** Ver HERMES-014. Adicionalmente: superfície de UI que lista plugins carregados/falhados com o erro, e um comando `hermes plugins doctor`.

**REGRESSION_TEST.** Plugin `security_critical` com import quebrado → o start falha com mensagem acionável.

---

## FINDING HERMES-016
```text
SEVERITY: P1 — HIGH
COMPONENT: Roteamento de modelos
FILE: apps/desktop/src/app/settings/omniroute-preset.ts ; custom-endpoints-settings.tsx
LOCATION: omniroute-preset.ts:1-6 ; custom-endpoints-settings.tsx:130-140, :170-200
```
**FACT.** O endpoint é `http://127.0.0.1:20128/v1`, fixo em código, sem chave de API e sem qualquer verificação de identidade do servidor. `validateCustomEndpoint(omniRoutePayload())` confirma apenas alcançabilidade e lista de modelos. O literal `20128` aparece em três arquivos distintos (`omniroute-preset.ts:2`, `omniroute-daily-health.py:13`, `docs:7`) sem fonte única.

**IMPACT.** Todo o tráfego de prompt do usuário — que inclui conteúdo de arquivos, trechos de código e potencialmente segredos — é enviado em texto claro para uma porta local não autenticada. Qualquer processo local que consiga ocupar a 20128 antes do OmniRoute recebe tudo e pode devolver completions envenenadas, que o agente então executa. Não há nada que distinga o OmniRoute legítimo de um impostor.

**RECOMMENDED_FIX.**
1. Token local obrigatório: o OmniRoute grava um segredo em `~/.omniroute` com permissão restrita; o Hermes lê e envia como `Authorization`. Recusar o endpoint se o token não validar.
2. Verificação de identidade: exigir um header/campo de identificação do OmniRoute na resposta de `/v1/models` e recusar se ausente.
3. Porta configurável, com uma constante compartilhada única (elimina HERMES-035 também).
4. Avisar na UI quando o endpoint responder mas não se identificar.

**REGRESSION_TEST.** Servidor falso em 20128 sem o token → o Studio recusa configurar e informa o motivo.

---

## FINDING HERMES-017
```text
SEVERITY: P2 — MEDIUM
COMPONENT: pt-BR / produto
FILE: apps/desktop/src/i18n/pt-br.ts
LOCATION: arquivo inteiro (449 linhas)
```
**FACT — medido.** Chaves-folha aproximadas por catálogo:
```text
en        3411 linhas   ~2452 chaves    (referência)
zh        3558 linhas   ~2613 chaves    ~107%
zh-hant   2879 linhas   ~2127 chaves     ~87%
ja        3001 linhas   ~2104 chaves     ~86%
ar        2757 linhas   ~1927 chaves     ~79%
pt-br      450 linhas    ~380 chaves     ~15%   ←
```
`defineLocale` (`define-locale.ts:39-41`) faz merge sobre `en`, então as chaves ausentes renderizam **em inglês**, silenciosamente.

**IMPACT.** O produto se descreve como *"designed for nontechnical users"* brasileiros (`docs:3`) e entrega ~84% da interface em inglês. É o defeito de produto com maior impacto sobre o público-alvo declarado. `README.md` anuncia "pt-BR" sem qualificar a cobertura.

**RECOMMENDED_FIX.**
1. Completar o catálogo priorizando: onboarding, configurações, erros, diálogos de confirmação, estados vazios, notificações e todo texto de aprovação/segurança (onde inglês é ativamente perigoso).
2. Teste de cobertura mínima por locale que falha abaixo de um limiar (ex.: 90% para locales anunciados como suportados).
3. Enquanto incompleto, marcar pt-BR como "parcial" na UI de seleção de idioma.

**REGRESSION_TEST.** Teste que percorre `Translations` recursivamente e compara o conjunto de chaves de cada locale contra `en`, reportando a porcentagem e falhando abaixo do limiar.

---

## FINDING HERMES-018
```text
SEVERITY: P2 — MEDIUM
COMPONENT: UI / indicador de segurança
FILE: apps/desktop/src/app/chat/right-rail/preview-browser-bar.tsx ; i18n/en.ts, pt-br.ts, zh.ts
LOCATION: preview-browser-bar.tsx:188-196 ; en.ts (preview.agentAccess)
```
**FACT.**
```tsx
<div aria-label={copy.agentAccessDescription}
     className="hidden items-center gap-1 … lg:flex" role="status">
  <Codicon name="shield" size="0.75rem" />
  {copy.agentAccess}
</div>
```
`agentAccess` é a string constante `'Agent access on'` / `'Acesso do agente ativo'`. Não há prop, estado ou condição — o chip é renderizado sempre, com ícone de escudo, e some abaixo do breakpoint `lg`.

**IMPACT.** Um indicador de segurança que sempre afirma o mesmo não informa nada e induz confiança indevida: o usuário passa a ler o escudo como confirmação de um estado que ninguém verificou. E some exatamente quando a janela é estreita.

**RECOMMENDED_FIX.** Vincular o chip ao estado real de acesso do agente à aba (ligado/desligado/pausado), com cores e texto distintos por estado; torná-lo visível em todas as larguras (colapsar para só o ícone com tooltip, não `hidden`); adicionar `aria-live` para leitores de tela quando o estado mudar.

**REGRESSION_TEST.** Teste de componente que renderiza com acesso desligado e assere que o texto **não** diz "ativo".

---

## FINDING HERMES-019
```text
SEVERITY: P2 — MEDIUM
COMPONENT: Instalação de bundles / documentação
FILE: apps/desktop/electron/bundled-product-studio.ts ; docs/hermes-omniroute-studio.md
LOCATION: bundled-product-studio.ts:39-58 ; docs:38
```
**FACT.** A doc afirma: *"it creates timestamped backups before changing a pre-existing managed target"*. `installManagedBundle` faz `fs.copyFileSync(source, destination)` direto, sem ler nem preservar o conteúdo anterior. Não existe a string `backup` em `bundled-product-studio.ts`.

**IMPACT.** Personalizações do usuário num diretório marcado como gerenciado são perdidas em toda atualização, contra uma promessa documentada de recuperabilidade.

**RECOMMENDED_FIX.** Implementar o backup (`<arquivo>.bak-<ISO8601>`), com retenção limitada e caminho exibido no log de instalação — ou remover a frase da documentação. Implementar é o certo, dado que a doc já criou a expectativa.

**REGRESSION_TEST.** Teste que modifica um arquivo gerenciado, roda a atualização e assere que o `.bak-` existe com o conteúdo antigo.

---

## FINDING HERMES-020
```text
SEVERITY: P2 — MEDIUM
COMPONENT: Redação de segredos
FILE: plugins/dz23-guardrail/__init__.py
LOCATION: :158-165 (_redact), :286-289 (escrita do relatório)
```
**FACT.**
```python
def _redact(value: str) -> str:
    try:
        from agent.redact import redact_sensitive_text
        return redact_sensitive_text(value, force=True)
    except Exception:
        return value          # ← relatório escrito SEM redação
```
O relatório inclui saída de `git status --short` e `git diff --stat` do workspace (`_git_summary`, `:167-198`) e é gravado em `<HERMES_HOME>/task-reports/` sem endurecimento de permissão.

**IMPACT.** Se o import falhar — layout diferente, ambiente empacotado, dependência ausente — o relatório vai para o disco sem redação, e nada sinaliza isso. `references/task-report.md:15` afirma *"Native secret redaction is applied before the file is written"*.

**RECOMMENDED_FIX.** Fail-closed: sem redator disponível, não escrever o relatório e registrar o motivo. Aplicar permissão restrita ao arquivo (0600 / ACL de usuário no Windows). Incluir no relatório uma linha explícita informando qual redator foi aplicado.

**REGRESSION_TEST.** Monkeypatch que faz o import falhar → assere que nenhum arquivo é criado e que o motivo é registrado.

---

## FINDING HERMES-021
```text
SEVERITY: P2 — MEDIUM
COMPONENT: Preset de configuração
FILE: apps/desktop/src/app/settings/omniroute-preset.ts ; omniroute-preset.test.ts
LOCATION: preset:52-105 ; test:63-72
```
**FACT.** `buildOmniRouteStudioConfig` sobrescreve incondicionalmente: `delegation.{max_concurrent_children, max_spawn_depth, orchestrator_enabled, child_timeout_seconds}`, `goals.max_turns`, `agent.{max_verify_nudges, verify_guidance}`, `approvals.{mode, cron_mode, single_query_mode, smart_policy}`, `memory.{memory_enabled, user_profile_enabled}`, `security.redact_secrets`, e todo o preset `moa.presets['dz23-moa']`.

O teste que se chama *"enables local cross-chat memory and **preserves existing configuration**"* verifica a preservação de `delegation.max_iterations: 250` — uma chave que o preset **não toca**. Nenhuma assertion cobre uma chave realmente sobrescrita.

**IMPACT.** O usuário que ajustou `goals.max_turns` ou `approvals.mode` perde o ajuste ao clicar em "Configurar OmniRoute", sem aviso. O teste dá a impressão de que isso está coberto.

**RECOMMENDED_FIX.** Distinguir "default se ausente" de "forçado". Só `mcp_servers.omniroute` e o preset `dz23-moa` justificam sobrescrita; o resto deve usar `??`. Exibir no diálogo o que será alterado antes de aplicar.

**REGRESSION_TEST.** Teste que passa `{goals:{max_turns:12}, approvals:{mode:'manual'}}` e assere que ambos sobrevivem.

---

## FINDING HERMES-022
```text
SEVERITY: P2 — MEDIUM
COMPONENT: Qualidade de testes
FILE: 8 sites
LOCATION:
  desktop-installation.test.ts:42, :56, :74
  fs-read-dir.test.ts:189
  git-review-ops.test.ts:42
  ssh-connection.test.ts:804, :820
  stage-native-deps.test.mjs:576
```
**FACT.** Todos usam `if (process.platform !== 'win32') { …assertion… }` ou `if (win32) return` **dentro do corpo do teste**. No Windows o teste executa, não assere a propriedade e **reporta PASS**.

**IMPACT.** A contagem de 1.549 PASS inclui testes que não verificam nada na plataforma de release. Isso é pior do que um skip: um skip é visível no relatório, um PASS vazio não. Três desses sites cobrem propriedades de segurança (modo 0600 do arquivo de identidade, recusa de control-dir symlink).

**RECOMMENDED_FIX.** Converter todos para `test.skipIf(...)` — mantendo a honestidade do relatório — e escrever o teste equivalente para Windows (ACL via `icacls`, junction em vez de symlink). Regra de lint de projeto que proíba `process.platform` dentro do corpo de um teste.

**REGRESSION_TEST.** A própria conversão; adicionar um teste de meta que falhe se `process.platform` aparecer dentro de um bloco `test(...)`.

---

## FINDING HERMES-023
```text
SEVERITY: P2 — MEDIUM
COMPONENT: Qualidade de testes
FILE: tests/skills/test_product_studio_skill.py ; tests/plugins/test_dz23_guardrail_plugin.py
LOCATION: skill test: arquivo inteiro ; plugin test: :16-24
```
**FACT.** As seis funções de `test_product_studio_skill.py` fazem exclusivamente asserções de substring sobre Markdown:
```python
assert "Never call local compilation production proof" in body
assert "Require explicit user intent before sensitive browser actions" in body
assert "make a CRM" in intake
```
Nenhum comportamento é exercitado. O teste falha se alguém reescrever uma frase e passa se o comportamento quebrar.

Em `test_dz23_guardrail_plugin.py:16-24`, `test_destructive_commands_are_blocked_by_hook` testa exatamente as três strings que os três regexes já casam — confirma o denylist contra si mesmo, sem um único caso adversarial. HERMES-005 mostra o que um caso adversarial encontra.

**IMPACT.** Inflam a contagem de testes sem aumentar a confiança, e criam a impressão de que a skill e o guardrail estão cobertos.

**RECOMMENDED_FIX.** Reduzir a validação da skill a um smoke de schema (frontmatter parseável, referências existem no disco, `platforms` correto) e mover o resto para testes de comportamento. Para o guardrail, ver HERMES-005.

---

## FINDING HERMES-024
```text
SEVERITY: P2 — MEDIUM
COMPONENT: Guardrails / falsos positivos
FILE: plugins/dz23-guardrail/__init__.py
LOCATION: :296-303
```
**FACT — provado por execução.**
```text
write_file com conteudo 'Nunca rode rm -rf / no servidor.'
  -> {'action':'block','message':'DZ23 Guardrail blocked a destructive operation matching rm -rf.'}
edit_file com conteudo '-- rollback: DROP TABLE tmp_import;'
  -> {'action':'block','message':'DZ23 Guardrail blocked a destructive operation matching DROP TABLE.'}
```
Causa: o padrão é aplicado a `serialized` — o JSON completo dos argumentos — e não apenas ao texto executável:
```python
if pattern.search(executable) or pattern.search(serialized):   # :297
```
**IMPACT.** O agente não consegue escrever documentação de segurança, um runbook, um `.gitignore` comentado ou uma migração SQL com rollback. Na prática, o usuário desabilita o guardrail — que é o pior desfecho possível para um controle de segurança.

**RECOMMENDED_FIX.** Casar apenas em `_command_text(args)` (campos `command`, `code`, `script`). Para ferramentas de escrita, avaliar somente o caminho de destino, nunca o conteúdo.

**REGRESSION_TEST.** Escrever um arquivo cujo conteúdo contém `rm -rf` e `DROP TABLE` → **não** bloqueia; executar `rm -rf` → bloqueia.

---

## FINDING HERMES-025
```text
SEVERITY: P2 — MEDIUM
COMPONENT: Goal
FILE: gateway/slash_commands.py ; hermes_cli/cli_commands_mixin.py
LOCATION: slash_commands.py:2859-2866 ; cli_commands_mixin.py:2994-3009
```
**FACT (a) — divergência.** No gateway a pausa é condicionada a `is_draft and state.has_contract()`. No CLI a condição é apenas `state.has_contract()`, e o comentário logo acima afirma *"Plain `/goal <text>` keeps its immediate behavior"* — o que o código contradiz: um `/goal <texto>` com linhas inline (ex.: `verify: pytest`) produz contrato e será pausado no CLI, mas não no gateway.

**FACT (b) — mensagem que pode mentir.** Ambos usam `state = mgr.pause(reason="awaiting-spec-review") or state`. Se `pause` retornar `None`, `state` fica inalterado e a resposta ainda diz *"Spec drafted and paused for review"* / *"Spec paused for review"*.

**IMPACT.** Mesma feature com dois comportamentos, e um caminho em que a UI afirma que o gate foi aplicado quando não foi. Para um gate de revisão isso é exatamente a classe de defeito que a missão proíbe.

**RECOMMENDED_FIX.** Extrair uma função única (`apply_goal_draft_gate`) consumida pelos dois; propagar falha de `pause` como erro visível; alinhar o comentário ao comportamento escolhido.

**REGRESSION_TEST.** Teste CLI equivalente ao `test_gateway_goal_draft_pauses_for_real_spec_review`; teste em que `pause` retorna `None` e assere que a mensagem **não** afirma pausa.

---

## FINDING HERMES-026
```text
SEVERITY: P2 — MEDIUM
COMPONENT: Aprovações / persistência de regra
FILE: tools/approval.py ; plugins/dz23-guardrail/__init__.py
LOCATION: approval.py:3841-3856, :3684-3687, :2949-2962 ; guardrail:322-328
```
**FACT.** `rule_key` fornecido pelo plugin vira `pattern_key = f"plugin_rule:{rule_key}"`, e a escolha `[a]lways` grava esse pattern em `command_allowlist` no `config.yaml` — auto-aprovação permanente entre sessões. O guardrail usa `f"dz23-guardrail:outside-workspace:{outside.parent}"`, ou seja granularidade por **diretório-pai**.

**IMPACT.** Um único `[a]lways` numa escrita legítima em, digamos, `C:\Users\zodyp\.ssh\known_hosts` autoriza permanentemente **todo** o diretório `.ssh`. Não há validação do `rule_key` vindo do plugin; um plugin mal escrito ou hostil pode escolher uma chave larga e converter um clique em autorização ampla.

**RECOMMENDED_FIX.** No core: prefixar obrigatoriamente `rule_key` com o id do plugin e recusar chaves que não sejam suficientemente específicas. No guardrail: usar o caminho completo do arquivo, não o diretório-pai. Na UI de aprovação: mostrar literalmente o escopo que `[a]lways` concede.

---

## FINDING HERMES-027
```text
SEVERITY: P2 — MEDIUM
COMPONENT: Caveman / compressão
FILE: apps/desktop/electron/omniroute-compression.ts ; main.ts
LOCATION: compression.ts:44-70 ; main.ts:14364-14376
```
**FACT.** `parseCompressionStatus` localiza o JSON por `clean.lastIndexOf('\n{')` e chama `JSON.parse` sem `try/catch`. Qualquer linha de log que contenha `\n{` desloca o ponto de corte. No handler `:get` a exceção é capturada e vira `unavailableCompressionStatus()` (honesto). No handler `:set` (`main.ts:14364`) não há captura — a exceção sobe crua para o renderer.

**IMPACT.** Falha frágil e mensagem de erro não traduzida/não acionável no toggle do Caveman. Baixa gravidade de segurança, gravidade real de confiabilidade percebida.

**RECOMMENDED_FIX.** Fazer a bridge emitir o JSON em stdout com um delimitador explícito (ou `--json` numa única linha, com todo log em stderr — a bridge já redireciona `console.log` para stderr, então basta garantir que só o resultado vá para stdout). Envolver o parse em `try/catch` e retornar erro tipado. Traduzir a mensagem.

---

## FINDING HERMES-028
```text
SEVERITY: P2 — MEDIUM
COMPONENT: Gate de verificação (runtime)
FILE: agent/conversation_loop.py ; agent/verify_hooks.py ; hermes_cli/plugins.py
LOCATION: conversation_loop.py:8188-8236 ; verify_hooks.py:21 ; plugins.py:6283-6329
```
**FACT.** `pre_verify` com `action: "continue"` injeta uma mensagem de usuário sintética e **continua** o turno. Teto `max_verify_nudges` = 3 por default. Após 3 nudges, o turno finaliza mesmo sem evidência. Uma diretiva sem `message`/`reason` não vazio é ignorada silenciosamente (`plugins.py:6324-6326`). O hook só dispara quando houve mutação de arquivo registrada em `_turn_file_mutation_paths`.

**IMPACT.** O `on_pre_verify` do guardrail é um lembrete, não um portão. Combinado com HERMES-006 (o gate é forjável) e HERMES-001 (o plugin não carrega), a afirmação de "delivery gates" do produto não tem sustentação em nenhuma das três camadas.

**RECOMMENDED_FIX.** Adicionar um modo estrito opcional (`verify.strict: true`) em que uma diretiva `block` de um plugin `security_critical` impede a finalização do turno e exige evidência ou uma dispensa explícita do usuário. Documentar claramente que o modo default é advisory.

---

## FINDING HERMES-029
```text
SEVERITY: P2 — MEDIUM   (ORIGEM: upstream)
COMPONENT: Electron / rede
FILE: apps/desktop/electron/main.ts
LOCATION: :5139-5155, :5205-5208, :14549
```
**FACT.** `fetchHtmlTitleWithCurl` coloca a URL vinda do renderer como último elemento do argv de `curl`, **sem `--` separador** e sem allowlist de esquema. `canonicalTitleCacheKey` (`:5139-5155`) retorna a string crua no `catch` de `new URL()`. Compare com `main.ts:12580`, que usa `--` corretamente antes do host SSH.

**IMPACT.** Argumentos como `--config`, `-o`, `-K` podem ser interpretados por `curl`; esquemas `file://`, `dict://`, `gopher://` habilitam leitura local e SSRF. **HYPOTHESIS** quanto à exploração.

**RECOMMENDED_FIX.** Inserir `--` antes da URL; validar esquema com allowlist `http|https`; usar `--proto '=http,https'` e `--proto-redir '=http,https'`.

---

## FINDING HERMES-030
```text
SEVERITY: P2 — MEDIUM
COMPONENT: Relatório de testes
FILE: apps/desktop (suíte)
```
**FACT.** Localizei estaticamente **6 sites de skip** que produzem **11 testes pulados** no Windows:

| # | Arquivo:linha | Testes | Motivo | Platform-specific de verdade? | Risco não testado no Windows |
|---|---|---|---|---|---|
| 1-7 | `hardening.test.ts:30` (posixTest) → :159, :386, :414, :439, :483, :510, :532 | 7 | Modo POSIX 0600 não existe no Windows | Sim | **Sim** — a proteção real de `connection.json` no Windows não tem substituto testado |
| 8 | `remote-lifecycle.test.ts:332` | 1 | Caminho POSIX de ciclo de vida remoto | Sim | Não |
| 9 | `update-handoff-marker.test.ts:101` | 1 | Hand-off POSIX (o par `:105` roda no Windows) | Sim | Não |
| 10 | `stage-native-deps.test.mjs:282` | 1 | `spawn-helper` do node-pty é darwin/linux | Sim | Não |
| 11 | `windows-remote-live.test.ts:28` | 1 | Exige `HERMES_WIN_SSH_{HOST,USER,HERMES}` | **Não** — é opt-in por ambiente | **Sim** — é o único teste de SSH real do produto |

**DIVERGÊNCIA.** O usuário reportou **12** pulados; identifiquei **11**. O 12º não é determinável estaticamente — pode vir de um skip dinâmico em runtime (`find-in-page-native.test.mjs` depende de binário nativo) ou da suíte Python. **Não vou inventar o 12º.**

**RECOMMENDED_FIX.** Fazer o runner imprimir a lista nomeada de skips com o motivo (`vitest --reporter=json` + um passo que renderize a tabela). Nenhum skip deve ser anônimo num produto que usa a contagem de testes como evidência de qualidade.

---

## FINDING HERMES-031
```text
SEVERITY: P2 — MEDIUM
COMPONENT: Relatório de tarefa
FILE: plugins/dz23-guardrail/__init__.py ; agent/conversation_loop.py ; hermes_cli/hooks.py
LOCATION: guardrail:381-397 ; conversation_loop.py:6699-6726 ; hooks.py:198-217
```
**FACT.** `on_post_api_request` espera `cost_usd=`. O payload real de `post_api_request` e o contrato documentado do hook não contêm esse campo — só `usage`. `report["cost_usd"]` permanece `0.0` e o relatório sempre imprime *"Monetary cost was not reported"* (`:264-266`).

**IMPACT.** Uma funcionalidade anunciada do relatório nunca produz dado. Não é grave, mas é exatamente "recurso declarado e não exercitado".

**RECOMMENDED_FIX.** Adicionar `cost_usd` ao payload do hook no core (o dado existe no roteamento) ou remover a seção do relatório. Preferir adicionar — controle de custo é útil para o público do produto.

---

## FINDING HERMES-032
```text
SEVERITY: P2 — MEDIUM
COMPONENT: MCP / contagem anunciada
FILE: README.md ; docs/hermes-omniroute-studio.md ; <omniroute>/open-sse/mcp-server
```
**FACT.** Enumeração estática do pacote `omniroute@3.8.49` instalado em `%APPDATA%\npm\node_modules\omniroute`:
```text
schemas/tools.ts (MCP_TOOL_MAP)    34
schemas/ccrTools.ts                 6   (re-exportadas de tools.ts)
schemas/pickFastestModel.ts         1
schemas/toolSearch.ts               1
tools/memoryTools.ts                3
tools/skillTools.ts                 4
tools/agentSkillTools.ts            3   (duplicadas de tools.ts)
tools/githubSkillTools.ts           3
tools/poolTools.ts                  6
tools/compressionTools.ts          13   (5 duplicadas de tools.ts)
tools/gamificationTools.ts          8
tools/pluginTools.ts                8
tools/notionTools.ts                6
tools/obsidianTools.ts             22
tools/localCorpusTools.ts           3
─────────────────────────────────────
TOTAL ÚNICO (de-duplicado)        106
ANUNCIADO                         107
```
**IMPACT.** Divergência de 1. Pode ser uma ferramenta que meu parser estático não capturou, ou o número anunciado pode estar desatualizado. Não é possível resolver sem um `tools/list` contra o servidor vivo.

**RECOMMENDED_FIX.** O servidor já calcula `TOTAL_MCP_TOOL_COUNT` via `countUniqueMcpTools` (`server.ts:104-117`). Gerar o número da documentação a partir dessa fonte em build, e nunca escrevê-lo à mão.

---

## FINDING HERMES-033
```text
SEVERITY: P2 — MEDIUM
COMPONENT: Segredos em repouso no Windows
FILE: apps/desktop/electron/hardening.test.ts ; hardening.ts
LOCATION: test:30, :159-560 ; hardening.ts:96-110
```
**FACT.** Os 7 testes que provam que `connection.json` — que contém o token remoto — é gravado owner-only são `test.skip` no Windows. `tightenSecretFileMode` depende de `stat.uid`/`chmod`, semântica que o Windows não implementa de forma equivalente. Não existe nenhum teste de ACL Windows.

**IMPACT.** Na única plataforma de release, a proteção em repouso do arquivo de credencial é **não verificada**. O token é criptografado por `safeStorage`, o que mitiga bastante — mas a propriedade que os testes afirmam garantir não é garantida onde importa.

**RECOMMENDED_FIX.** Implementar e testar endurecimento por ACL no Windows (`icacls <arquivo> /inheritance:r /grant:r "%USERNAME%":F`) e asserir o resultado lendo a ACL de volta. Manter os testes POSIX como estão.

---

## FINDING HERMES-034
```text
SEVERITY: P2 — MEDIUM   (ORIGEM: upstream)
COMPONENT: Auto-update
FILE: apps/desktop/electron/main.ts
LOCATION: :2998-3024, :3556, :14627-14632
```
**FACT.** Em `repairMacUpdaterHelper`, quando o binário do updater **falha** `codesign --verify`, o código não aborta: remove o atributo de quarentena (`xattr -cr`) e **assina ad-hoc** o binário não confiável (`codesign --force --sign -`) para que o Gatekeeper o execute. Chamado em `:3556`, imediatamente antes do handoff. Separadamente, `hermes:updates:branch:set` (`:14627`) aceita qualquer nome de branch vindo do renderer, e o "feed" de update é `git ls-remote` sem verificação de assinatura de commit ou tag.

**IMPACT.** Verificação de assinatura invertida em fail-open. Quem gravar no caminho do updater staged tem o binário sancionado e executado. Escopo macOS; o produto é Windows, mas o código está no stage e será mantido.

**RECOMMENDED_FIX.** Falhar quando `codesign --verify` falhar, nunca re-assinar. Restringir a branch de update a uma allowlist definida no build. Verificar assinatura de tag/commit ou publicar um manifesto assinado.

---

## FINDING HERMES-035
```text
SEVERITY: P2 — MEDIUM
COMPONENT: Cron / health check
FILE: integrations/omniroute-daily-health.py
LOCATION: :13, :31-35
```
**FACT.** `MODELS_URL = "http://127.0.0.1:20128/v1/models"` é a terceira cópia do literal (ver HERMES-016), enquanto `OMNIROUTE_HOME` é configurável por env — inconsistência de configurabilidade. A contagem de erros usa `LEVEL_PATTERN.finditer(line)` e soma **cada ocorrência** da palavra na linha, incluindo ocorrências dentro de conteúdo de usuário ecoado no log. Não há teste.

**IMPACT.** Métrica de saúde inflada e enganosa, exatamente o tipo de sinal que leva alguém a concluir "está tudo bem" sem base.

**RECOMMENDED_FIX.** Constante compartilhada única para o endpoint (respeitando a mesma env que o resto do sistema); parse por nível estruturado do log em vez de regex sobre a linha inteira; contar no máximo uma vez por linha; adicionar teste com um log de fixture.

---

## FINDING HERMES-036
```text
SEVERITY: P3 — LOW
COMPONENT: Higiene de revisão
FILE: apps/desktop/scripts/stage-native-deps.test.mjs ; test-desktop.mjs
```
**FACT.** Grande parte do diff nesses arquivos é reformatação Prettier (quebra de linha, aspas), misturada com duas mudanças de comportamento reais (a assertion condicional em `:576` e a parametrização de nomes). Isso dificulta a revisão exatamente onde ela importa.

**RECOMMENDED_FIX.** Separar em dois commits: `style: prettier` e `feat/fix: <mudança>`. Adicionar o hash do commit de formatação a `.git-blame-ignore-revs`.

---

## FINDING HERMES-037
```text
SEVERITY: P3 — LOW
COMPONENT: Resolução de path
FILE: apps/desktop/electron/windows-hermes-path.ts
LOCATION: :137, :162
```
**FACT.** `path.join` → `path.win32.join` / `path.posix.join`. Em Windows real ambos são idênticos, então a mudança é no-op em produção; ela existe para que a função possa ser exercitada a partir de um host de outra plataforma.

**RECOMMENDED_FIX.** Injetar o módulo `path` como dependência opcional (`options.path = path`) em vez de fixar a variante — mantém o teste possível sem código que só existe para o teste.

---

## FINDING HERMES-038
```text
SEVERITY: P3 — LOW
COMPONENT: Build / identidade do executável
FILE: apps/desktop/scripts/set-exe-identity.mjs
LOCATION: :45-56
```
**FACT.** `Number.parseInt(part, 10) || 0` converte silenciosamente uma parte não numérica em `0` (`'1.x.3'` → `1.0.3`). Não há clamp em 65535, limite de cada campo de versão PE.

**RECOMMENDED_FIX.** Validar e lançar erro explícito em versão malformada; clampar/validar contra 65535 com mensagem clara.

---

## FINDING HERMES-039
```text
SEVERITY: P3 — LOW
COMPONENT: Manifesto do plugin
FILE: plugins/dz23-guardrail/plugin.yaml
LOCATION: :5-20
```
**FACT.** `provides_hooks` e `hooks` listam exatamente os mesmos 7 nomes. Uma das duas chaves é ignorada pelo loader; manter ambas cria risco de divergirem.

**RECOMMENDED_FIX.** Manter apenas a chave que o loader lê e adicionar `kind: backend` e `security_critical: true` (HERMES-001, HERMES-015).

---

## FINDING HERMES-040
```text
SEVERITY: P3 — LOW
COMPONENT: i18n
FILE: apps/desktop/src/i18n/languages.ts
LOCATION: :88-94
```
**FACT.** `LOCALE_ALIASES` inclui `português` (acentuado) mas não `portugues`. Um valor persistido ou digitado sem acento não resolve para pt-br.

**RECOMMENDED_FIX.** Normalizar a entrada removendo diacríticos (`.normalize('NFD').replace(/\p{Diacritic}/gu,'')`) antes de consultar o mapa.

---

## FINDING HERMES-041
```text
SEVERITY: P3 formalmente — OPERACIONALMENTE URGENTE
COMPONENT: Git / preservação do trabalho
FILE: repositório
```
**FACT.** `feature/hermes-omniroute-studio` == `origin/main` == `e30388e (grafted)`. Zero commits locais. As 3.192 linhas de trabalho do OmniRoute existem **apenas no índice**. Clone raso, sem histórico.

**IMPACT.** Não há finding de segurança aqui — há risco de perda total. `git reset`, `git checkout`, `git stash drop`, corrupção do índice ou uma ferramenta que "limpe" o repositório destrói tudo, sem reflog para recuperar (objetos staged existem em `.git/objects` mas sem árvore nomeada são coletados pelo `gc`).

**RECOMMENDED_FIX — fazer isto antes de qualquer outra coisa, e é o único ponto em que recomendo escrita no repositório:**
```powershell
cd C:\Users\zodyp\Documents\Codex\Hermes-OmniRoute
git stash create                      # NÃO — não usar
# Correto, não destrutivo, preserva o índice:
git bundle create ..\hermes-omniroute-index-backup.bundle --all
git diff --cached > ..\hermes-omniroute-staged-backup.diff
```
E, quando você autorizar, um commit real na branch de feature (sem push). Enquanto não houver commit, **nenhuma ferramenta deve rodar `reset`, `clean`, `checkout` ou `restore` neste repositório**.
