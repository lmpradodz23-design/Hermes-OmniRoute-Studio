# HERMES OMNIROUTE — AUDITORIA R2 (verificação de remediação)

Auditor independente · 2026-08-21 · escopo: `C:\Users\you\Documents\Codex\Hermes-OmniRoute`

> **Esta rodada não repete a anterior.** O projeto mudou de forma substancial entre as duas auditorias. O trabalho aqui foi: reancorar o estado, **re-executar** os bypasses que eu havia provado, e separar com evidência o que foi corrigido do que continua aberto.

---

## 1. ESTADO VERIFICADO (comandos reais, saída real)

```text
diretório atual   /…/Hermes-OmniRoute
raiz do Git       /…/Hermes-OmniRoute            (idênticos)
branch            feature/hermes-omniroute-studio          ✔ conforme esperado
HEAD              9d80176ad6761949775b354d37be8678dea843b5 ✔ = baseline informada
commit HEAD       "feat: add Hermes OmniRoute Studio integration baseline"
                  lmprado.dz23 · Fri Aug 21 04:30:16 2026 -0300
                  58 files changed, 3192 insertions(+), 189 deletions(-)
main              e30388e [origin/main: ahead 1, behind 1]
git diff --check  rc=0 (sem whitespace error)
staged            0
stash             vazio
```

**Mudança relevante desde a auditoria anterior:** os 58 arquivos que estavam apenas no índice **foram commitados** em `9d80176`. O risco de perda total (meu HERMES-041) está **resolvido**.

### Worktree — alterações intencionais não commitadas

```text
git diff --stat (12 arquivos rastreados)          +1080 / -317
  apps/desktop/electron/bundled-product-studio.ts       +95
  apps/desktop/electron/bundled-product-studio.test.ts  +89
  apps/desktop/electron/entitlements.mac.inherit.plist  +32
  apps/desktop/electron/entitlements.mac.plist          +32
  apps/desktop/electron/fs-ipc.ts                       +30
  apps/desktop/electron/main.ts                        +291
  apps/desktop/electron/omniroute-compression.ts         +3
  apps/desktop/electron/preload.ts                       +5
  apps/desktop/electron/preview-reach.e2e.mts          +270
  integrations/omniroute-mcp-bridge.mjs                +375
  plugins/dz23-guardrail/__init__.py                   +165
  plugins/dz23-guardrail/plugin.yaml                    +10

+ hermes_cli/plugins.py    278.364 → 283.274 bytes   ** núcleo Python alterado **
+ tools/approval.py        246.970 → 250.063 bytes   ** núcleo Python alterado **

untracked (código, não auditoria):
  apps/desktop/electron/content-security.ts        + .test.ts
  apps/desktop/electron/security-boundaries.ts
  apps/desktop/electron/omniroute-local-auth.ts    + .test.ts
  apps/desktop/electron/omniroute-security.test.ts
  integrations/omniroute-mcp-policy.mjs
```

**Preservei tudo.** Nenhum `reset`, `clean`, `checkout`, `restore`, `stash`, commit ou push. As únicas escritas foram em `audit/_raw/` (diffs e tarballs de trabalho) e `audit/` (relatórios), ambos untracked e fora do índice.

### Hashes

```text
INSTALADOR
  arquivo   …\2026-08-20\in\outputs\Hermes-OmniRoute-Studio-0.17.0-omniroute.1-final-win-x64.exe
  tamanho   118.521.325 bytes
  sha256    e4c822706dcac961616080aa9324bd255bd437015b95d52ad87ad0c73dc67490
  esperado  E4C822706DCAC961616080AA9324BD255BD437015B95D52AD87AD0C73DC67490
  RESULTADO ✔ CONFERE

EXECUTÁVEL INSTALADO
  arquivo   …\AppData\Local\Programs\HermesOmniRoute\HermesOmniRoute.exe
  tamanho   214.007.808 bytes
  sha256    04e295f6a4e69bd82659d3c36b3320b183861a9161c892051a5e34e4ab066481
  esperado  não fornecido — registrado como linha de base para comparações futuras
```

### A build instalada contém o código atual do repositório?

**Sim — e mais do que ele.** Não é uma build antiga; é uma build de trabalho **não commitado**.

```json
resources/install-stamp.json
{ "schemaVersion": 1,
  "commit": "9d80176ad6761949775b354d37be8678dea843b5",
  "branch": "feature/hermes-omniroute-studio",
  "builtAt": "2026-08-21T16:34:03.013Z",
  "dirty": true,          ← o próprio carimbo declara worktree sujo
  "source": "local" }
```

Paridade byte-a-byte entre `resources/` da instalação e o worktree atual:

| Componente | commit `9d80176` | worktree | instalado |
|---|---|---|---|
| `omniroute-mcp-bridge.mjs` | 2.337 | **13.474** | **13.474** |
| `omniroute-mcp-policy.mjs` | **ausente** | **3.661** | **3.661** |
| `dz23-guardrail/__init__.py` | 14.859 | **19.603** | **19.603** |
| `dz23-guardrail/plugin.yaml` | 479 | **379** | **379** |
| `omniroute-daily-health.py` | 2.087 | 2.087 | 2.087 |

**Conclusão (FATO):** a build instalada e o instalador cujo SHA-256 confere correspondem ao **worktree atual**, não ao commit. O `commit` no `install-stamp.json` é, isoladamente, enganoso — a proveniência real é "commit `9d80176` **mais um delta não versionado**". Ver `R2-NEW-03`.

---

## 2. RE-EXECUÇÃO DOS BYPASSES QUE EU HAVIA PROVADO

Carreguei o `plugins/dz23-guardrail/__init__.py` **atual** (19.603 bytes) e repeti os testes.

> Aproximação declarada: o guardrail agora delega a `tools.approval._command_detection_variants`. Para isolar o teste, substituí esse parser por um stub que produz a variante crua **e** a variante com barras invertidas achatadas — que é o comportamento essencial do núcleo (`tools/approval.py:2292-2298`). Os padrões testados são os reais do guardrail.

```text
=== denylist destrutivo ===
  BLOQUEADO | del /s /q C:\Users\you\Documents
  BLOQUEADO | rd /s /q C:\projeto
  BLOQUEADO | Remove-Item -Recurse -Force C:\Users\you
  BLOQUEADO | rm -r -f /tmp/x
  BLOQUEADO | rm --recursive --force /tmp/x
  BLOQUEADO | find . -delete
  BLOQUEADO | git clean -fdx
  BLOQUEADO | git reset --hard
  BLOQUEADO | git push --force origin main
  BLOQUEADO | DROP DATABASE producao
  BLOQUEADO | TRUNCATE TABLE users
  BLOQUEADO | docker volume prune -f
  BLOQUEADO | docker image prune -a
  BLOQUEADO | vssadmin delete shadows /all
  BLOQUEADO | reg delete HKLM\Software\X /f
  BLOQUEADO | takeown /f C:\ /r
  BLOQUEADO | rm -rf /tmp/x
  BLOQUEADO | shutil.rmtree("C:/x")
  --> 18/18                       (antes: 1/12)

=== negativos — NÃO podem bloquear ===
  ok | git clean -n
  ok | git clean --dry-run
  ok | npm ci
  ok | ls -la
  ok | echo "rm -rf /" >> notas.txt
  --> 5/5 corretos                (antes: falso positivo em documentação)

=== escrita fora do workspace ===
  '../../../../home/user/.ssh/authorized_keys' -> approve   (antes: None = liberado)
  './../../etc/passwd'                          -> approve   (antes: None = liberado)
  'sub/ok.txt'                                  -> None      (dentro do workspace, correto)

=== gate de verificação ===
  só escrita, sem verificação   -> EXIGE evidência
  echo npm test                 -> EXIGE evidência          (antes: satisfazia o gate)
  npm test que falhou (string)  -> EXIGE evidência          (antes: satisfazia o gate)
  npm test exit_code=1          -> EXIGE evidência
  npm test exit_code=0          -> satisfeito (correto)
  pytest exit_code=0            -> satisfeito (correto)     (antes: pytest não casava)
  resultado sem exit_code       -> EXIGE evidência (fail-closed)

=== falso positivo em conteúdo de arquivo ===
  doc citando "rm -rf /"        -> None (não bloqueia)      (antes: bloqueava)
  SQL com "DROP TABLE tmp"      -> None (não bloqueia)      (antes: bloqueava)

=== raiz de confiança sem workspace resolvível ===
  cwd=/  roots = ()  →  write /etc/passwd -> approve        (antes: liberado)
```

**Os seis achados que eu havia provado por execução estão corrigidos.** Não há mais `Path.cwd()` nem `/workspace` fixo como raiz de confiança: `_workspace_roots()` agora usa `agent.runtime_cwd.resolve_agent_cwd()` e, quando não resolve, retorna vazio — e `_outside_workspace` trata conjunto vazio como "fora", ou seja, fail-closed.

---

## 3. VERIFICAÇÃO DOS DEMAIS ACHADOS P0/P1

| ID anterior | Status | Evidência |
|---|---|---|
| **HERMES-001** guardrail nunca carrega | ✅ **CORRIGIDO** | `plugin.yaml` agora tem `kind: backend` + `security_critical: true`. `hermes_cli/plugins.py` auto-carrega `source==bundled && kind==backend`. Além disso, novo escaneamento de plugins do Studio em namespace próprio, deliberadamente **por último** para que um plugin de usuário não possa sombrear o guardrail reusando o nome do manifesto. |
| **HERMES-002** RCE via `OMNIROUTE_PACKAGE_ROOT` | ✅ **CORRIGIDO** | Novo `integrations/omniroute-mcp-policy.mjs`: allowlist de raízes de instalação, `fs.promises.realpath` canônico, comparação case-insensitive no Windows, verificação de `package.json.name === 'omniroute'`, faixa de versão `>=3.8.49 <4.0.0`, e carga de `dist/open-sse/mcp-server/server.js` **compilado** (sem `tsx` em runtime). Confirmei que esse `server.js` existe (4.167.523 bytes) e que o pacote é `omniroute@3.8.49`. |
| **HERMES-003** escopos MCP auto-concedidos | ✅ **CORRIGIDO** | `DEFAULT_OMNIROUTE_MCP_SCOPES` = `execute:completions, read:combos, read:health, read:models, read:quota, read:usage`. Os 32 escopos anteriores caíram para 6. **`write:plugins` removido** — a superfície de execução de código via `plugin_install` fechou. |
| **HERMES-004** renderer → execução local | ✅ **CORRIGIDO** | Novo `security-boundaries.ts`: `resolveAllowedFsIpcPath` com `fs.realpathSync.native` e ancestral canônico (cobre junction/symlink e caminho-folha inexistente); `externalFileBlockReason` bloqueia arquivos sensíveis e executáveis. `fs-ipc.ts` roteia `readDir`, `gitRoot`, `reveal`, `openDir`, `rename` por `resolveAllowedPath`. `openExternalUrl` aplica ambos no ramo `file:`. Raízes = `HERMES_HOME` + Downloads + projeto padrão + seleções nativas do usuário. |
| **HERMES-009** erro de I/O aborta o boot | ✅ **CORRIGIDO** | `installManagedComponents({...})` recebe thunks e devolve `ManagedComponentState`; novo IPC `hermes:omniroute:managed:status` expõe o estado à UI. |
| **HERMES-010** escreve no runtime do Hermes original | ✅ **CORRIGIDO** | `resolveStudioManagedPaths(HERMES_HOME)` cria namespace próprio; `HERMES_STUDIO_PLUGIN_ROOT` é passado ao backend e **validado** no Python (`get_studio_managed_plugins_dir`) contra o caminho canônico esperado — uma env hostil não transforma diretório arbitrário em fonte confiável. Desinstalação reverte apenas o que tem marcador de propriedade. |
| **HERMES-011** `npm/pip install` sem gate | ⚠️ **PARCIAL** | `DANGEROUS_PATTERNS` ganhou 3 padrões que distinguem **restaurar lockfile** (não casa: `npm ci`, `pip install -r`, `uv sync --frozen`) de **nomear pacote novo** (casa). Correto e bem pensado. **Mas** — ver `R2-NEW-05`. |
| **HERMES-013** sem CSP, webview sem handler | ✅ **CORRIGIDO** | `content-security.ts` + `installRendererContentSecurity()`: CSP via `onHeadersReceived` (`script-src 'self' 'wasm-unsafe-eval'`, sem `unsafe-inline`/`unsafe-eval`, `object-src 'none'`, `base-uri 'none'`, `frame-ancestors 'none'`); `web-contents-created` + `will-attach-webview` com `hardenWebviewAttachment` que apaga `preload`, força as flags e fixa a partition; `will-navigate` **e** `will-redirect` agora usam `isTrustedRendererNavigation`, que compara o caminho exato do índice do renderer em vez de `startsWith('file:')`; handlers de permissão passaram a exigir origem confiável. |
| **HERMES-014** `pre_tool_call` fail-open | ⚠️ **PARCIAL** | `plugins.py` agora rastreia `_security_critical_hook_callbacks`; exceção em callback crítico injeta `{"action":"block"}`. **Mas** ver `R2-NEW-07`. |
| **HERMES-015** falha de plugin de segurança silenciosa | ✅ **CORRIGIDO** | Falha de carga de plugin `security_critical` levanta `RuntimeError("… startup aborted …")`. |
| **HERMES-016** endpoint 20128 sem auth | ✅ **CORRIGIDO** | `omniroute-local-auth.ts`: token local em `safeStorage`, com expiração, provisionado no processo main, entregue ao backend por env (`OMNIROUTE_MCP_TOKEN`) e **nunca devolvido ao renderer nem persistido em `config.yaml`** — o comentário no código declara isso explicitamente. Revogado na desinstalação. |
| **HERMES-019** doc promete backup inexistente | ✅ **CORRIGIDO** | `backupManagedDirectory` / `backupManagedFile` gravam em `.omniroute-backups/<snapshot>` com carimbo ISO antes de sobrescrever. |
| **HERMES-039** `plugin.yaml` duplicado | ✅ **CORRIGIDO** | Chave `hooks:` duplicada removida. |
| **HERMES-041** trabalho sem commit | ✅ **RESOLVIDO** | Commit `9d80176` criado. |

---

## 4. AINDA ABERTO — arquivos que não foram tocados

Verificado por comparação de tamanho `commit HEAD` × worktree:

```text
agent/tool_executor.py                                       INTOCADO
apps/desktop/src/app/chat/right-rail/preview-browser-bar.tsx INTOCADO
apps/desktop/electron/desktop-installation.test.ts           INTOCADO
apps/desktop/electron/ssh-connection.test.ts                 INTOCADO
apps/desktop/electron/hardening.test.ts                      INTOCADO
apps/desktop/scripts/stage-native-deps.test.mjs              INTOCADO
apps/desktop/electron/hardening.ts                           INTOCADO
integrations/omniroute-daily-health.py                       INTOCADO
gateway/slash_commands.py                                    INTOCADO
hermes_cli/cli_commands_mixin.py                             INTOCADO
```

| ID | Sev | Status |
|---|---|---|
| **HERMES-017** pt-BR incompleto | **P1** | pt-br.ts foi ampliado (449 → 586 linhas) mas a cobertura foi de **15,5% → 18,2%** (≈449 de ≈2.463 chaves). `defineLocale` faz merge sobre `en`, então **~82% da interface continua em inglês** para o público-alvo declarado. É agora o maior defeito de produto em aberto. |
| **HERMES-018** indicador de segurança estático | P2 | `preview-browser-bar.tsx` intocado. O chip "Acesso do agente ativo" continua texto fixo sem binding, e continua `hidden … lg:flex`. |
| **HERMES-012** SSH: caminho Windows sem cobertura | P1 | `ssh-connection.test.ts` intocado — os 9 `mux: true` continuam forçando o caminho multiplexado; o caminho real do Windows segue sem teste, e o único teste live continua `skipIf` sem host. |
| **HERMES-022** 8 assertions viram no-op no Windows | P2 | Os 4 arquivos de teste envolvidos estão intocados. Continuam reportando PASS sem asserir. |
| **HERMES-033** proteção de `connection.json` no Windows | P2 | `hardening.test.ts` e `hardening.ts` intocados; 7 testes seguem `test.skip` no Windows, sem equivalente por ACL. |
| **HERMES-025** Goal: divergência CLI × gateway | P2 | Ambos intocados. `mgr.pause(...) or state` continua podendo afirmar "pausado" quando a pausa falhou. |
| **HERMES-035** health check com métricas grosseiras | P2 | Intocado. |
| **HERMES-023** testes que verificam Markdown | P2 | `tests/skills/test_product_studio_skill.py` intocado. |
| **HERMES-032** 106 × 107 ferramentas MCP | P2 | Não resolvível estaticamente; exige `tools/list` contra o servidor vivo. |
| **HERMES-030** 12º teste pulado | P2 | Continua não identificável sem a saída real da suíte. |

---

## 5. ACHADOS NOVOS DESTA RODADA

### R2-NEW-01 · P1 · Código de segurança inteiro está untracked
```text
COMPONENTE  Git / integridade da correção
FATO        Estes arquivos NÃO estão em nenhum commit:
              apps/desktop/electron/content-security.ts        (+ .test.ts)
              apps/desktop/electron/security-boundaries.ts
              apps/desktop/electron/omniroute-local-auth.ts    (+ .test.ts)
              apps/desktop/electron/omniroute-security.test.ts
              integrations/omniroute-mcp-policy.mjs
```
Toda a remediação de HERMES-002, 003, 004, 013 e 016 vive fora do controle de versão. Um `git clean -fd` — que o Codex está proibido de rodar, mas qualquer ferramenta ou IDE pode — apaga a correção de quatro P0. Além disso: não está em nenhum diff revisável, não entra em CI, e não sobrevive a um clone novo.
**CORREÇÃO:** commitar. É o item mais urgente desta rodada, pelo mesmo motivo que HERMES-041 era o mais urgente da anterior.

### R2-NEW-02 · P1 · `smart_policy` contradiz o guard recém-criado
```text
ARQUIVO  apps/desktop/src/app/settings/omniroute-preset.ts:81-82
         tools/approval.py:774-799
```
`tools/approval.py` ganhou três padrões deliberados, com o comentário: *"naming a new package mutates the dependency graph and may immediately execute untrusted lifecycle hooks. Keep this an approvable warning (rather than a hard block) **so the user can inspect the package/version before it runs**"*.

O preset do Studio, na mesma árvore, define `approvals.mode: 'smart'` com:
> *"Auto-approve read-only inspection, tests, builds, **dependency installation**, and reversible writes…"*

O guard leva o comando ao aprovador; o aprovador é um LLM; e a política do operador manda aprovar exatamente a categoria que o guard existe para segurar. O usuário nunca vê o nome do pacote.
**CORREÇÃO:** remover "dependency installation" da `smart_policy`, ou qualificar para "instalação a partir de lockfile já declarado". A detecção nova só entrega valor se a política parar de anulá-la.

### R2-NEW-03 · P2 · Instalador publicado não corresponde a nenhum commit
`install-stamp.json` traz `"dirty": true`. O SHA-256 confere com o esperado — o artefato é o que se diz que é — mas sua **fonte** não é reproduzível: é `9d80176` mais um delta não versionado que só existe na máquina do desenvolvedor. Ninguém consegue reconstruir esse binário.
**CORREÇÃO:** proibir build de release com worktree sujo (falhar o script quando `dirty`), ou carimbar o hash do delta e anexá-lo ao artefato.

### R2-NEW-04 · P2 · Lista de extensões executáveis incompleta para Windows
```text
ARQUIVO  apps/desktop/electron/security-boundaries.ts:18-30
```
`EXECUTABLE_FILE_EXTENSIONS` cobre `.bat .cmd .com .exe .jar .js .lnk .msi .ps1 .scr .vbs`. Faltam vetores clássicos de execução por associação no Windows: **`.hta` `.wsf` `.wsh` `.jse` `.vbe` `.reg` `.url` `.scf` `.pif` `.cpl` `.msc` `.msp` `.appref-ms` `.ps2` `.psc1` `.chm` `.sct`**. `shell.openPath` num `.hta` executa `mshta.exe`; num `.url` ou `.scf` pode disparar navegação/SMB.
**CORREÇÃO:** ampliar a lista; melhor ainda, inverter para allowlist de extensões seguras para abertura externa.

### R2-NEW-05 · P2 · Seleção nativa pode promover a raiz de um drive a raiz permitida
```text
ARQUIVO  apps/desktop/electron/main.ts (approveNativeSelectedPath)
FATO     nativeApprovedFsRoots.add(path.resolve(directory ? selectedPath : path.dirname(selectedPath)))
```
Se o usuário escolher um arquivo em `C:\` pelo diálogo nativo, `path.dirname` devolve `C:\` e o drive inteiro entra em `desktopAllowedFsRoots()` pelo resto da sessão — anulando o confinamento de `resolveAllowedFsIpcPath` para todo o disco.
**CORREÇÃO:** recusar raízes que sejam o anchor de um drive ou o diretório home; conceder por arquivo em vez de por diretório-pai quando a seleção for de arquivo.

### R2-NEW-06 · P2 · `frame-src` permite HTTP em texto claro
```text
ARQUIVO  apps/desktop/electron/content-security.ts:9
         "frame-src 'self' https: http:"
```
A CSP é sólida no essencial, mas `frame-src http:` (e `img-src`/`media-src http:`) permite enquadrar e carregar conteúdo não criptografado de qualquer host. Para preview local `http://127.0.0.1:*` é necessário; `http:` global não é.
**CORREÇÃO:** restringir a `http://127.0.0.1:* http://localhost:*` como já foi feito, corretamente, em `connect-src`.

### R2-NEW-07 · P2 · O fail-closed do plugin crítico é anulado uma camada acima
```text
ARQUIVO  agent/tool_executor.py (INTOCADO)
FATO     except Exception:
             return None      ← "sem diretiva de bloqueio" → a ferramenta EXECUTA
```
`plugins.py` agora converte exceção **dentro de um callback crítico** em `{"action":"block"}` — correto. Mas o dispatcher externo continua engolindo qualquer exceção que escape antes disso e devolvendo `None`. A garantia fail-closed vale só até essa camada.
Relevante em concreto: o guardrail novo faz `from tools.approval import _command_detection_variants` **sem `try/except`** (`__init__.py:164-166`). Nesse caminho específico a exceção nasce dentro do callback e é convertida em `block` — ok. Mas qualquer falha em `_dispatch_pre_tool_call_hooks` antes do invoke ainda libera a ferramenta.
**CORREÇÃO:** no `tool_executor`, quando houver ao menos um hook `security_critical` registrado, converter exceção em bloqueio em vez de `None`.

### R2-NEW-08 · P3 · `python`/`py` cobertos, mas `uv pip install` não
```text
ARQUIVO  tools/approval.py:795-799
```
O padrão Python cobre `pip`, `pipN`, `python -m pip`, `py -m pip`. Não cobre `uv pip install <pkg>` nem `poetry add` / `pdm add` / `conda install` — gerenciadores em uso corrente.
**CORREÇÃO:** estender o padrão.

---

## 6. O QUE CONTINUA `NOT_TESTED` — e por quê

Os comandos que você listou (`npm run typecheck`, `npm run lint`, `npm test`) **não foram executados**, pelo mesmo motivo da rodada anterior e sem contorno disponível daqui:

```text
BLOCKED_BY_EXTERNAL_DEPENDENCY
dependency=  toolchain Windows (Electron, electron-builder, NSIS, vitest da suíte desktop)
affected_feature= typecheck, lint, 1.549 testes Electron, build, NSIS, app instalado,
                  DevTools, processos, RAM/CPU, preview, cron, MCP vivo, OmniRoute :20128
what_was_verified= estado Git, hashes, paridade build×fonte, todo o código-fonte relevante,
                   e EXECUÇÃO REAL do plugin de guardrail (18/18 + 5/5 + 7 casos de gate)
what_could_not_be_verified= qualquer coisa que exija rodar binário Windows ou rede local
exact_requirement_to_unblock= executar na máquina Windows, ou conceder computer use nela
```

Este ambiente é um container Linux com as pastas montadas por bridge de arquivo. `device_bash` roda numa VM Linux separada, sem acesso à rede local do Windows — por isso `http://127.0.0.1:20128` também é inalcançável e **toda a seção C (Caveman) e a matriz MCP permanecem `NOT_TESTED`**. Os números que você citou continuam **não confirmados por mim**.

---

## 7. VEREDITO

```text
VERDICT=APPROVED_WITH_FINDINGS

P0_ABERTOS=0        (4 → 0; todos verificados corrigidos)
P1_ABERTOS=5        R2-NEW-01, R2-NEW-02, HERMES-012, HERMES-017, (HERMES-011 parcial)
P2_ABERTOS=13
P3_ABERTOS=5

GIT_STATE_PRESERVED=YES
GIT_COMMIT_CREATED=NO
GIT_PUSH_PERFORMED=NO
INSTALLER_SHA256=MATCH
INSTALLED_BUILD_MATCHES_SOURCE=YES (worktree, não commit — dirty:true)
GUARDRAIL_BYPASSES_REEXECUTED=6/6 CORRIGIDOS
```

O trabalho de remediação entre as duas auditorias foi sério e, no que consegui executar, **funciona**. As quatro falhas críticas foram fechadas na causa raiz, não maquiadas: o guardrail passou a usar o parser real do núcleo em vez de regex própria, o gate de verificação passou a exigir exit code em vez de heurística de texto, os escopos MCP caíram de 32 para 6, e o bridge deixou de executar TypeScript de caminho controlado por env.

O que impede um veredito melhor é bem específico e não é técnico: **a correção de quatro P0 está fora do controle de versão**. Enquanto `content-security.ts`, `security-boundaries.ts`, `omniroute-local-auth.ts` e `omniroute-mcp-policy.mjs` não estiverem commitados, o produto está a um comando de distância de regredir inteiramente — e o instalador que você já distribuiu não é reconstruível por ninguém.
