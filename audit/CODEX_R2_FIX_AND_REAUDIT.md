# CODEX — CORREÇÃO R2 + AUDITORIA INDEPENDENTE PÓS-CORREÇÃO

> Documento autossuficiente. Leia inteiro antes de tocar em qualquer arquivo.
> Projeto: `C:\Users\you\Documents\Codex\Hermes-OmniRoute`
> Branch: `feature/hermes-omniroute-studio` · HEAD esperado: `9d80176ad6761949775b354d37be8678dea843b5`

---

## 0. REGRAS INEGOCIÁVEIS

> Você não está autorizado a esconder problemas para obter um pipeline verde.
> Corrija a causa raiz.
> Não remova testes para fazê-los passar. Não enfraqueça assertions.
> Não substitua integrações reais por mocks para declarar sucesso.
> Não transforme FAIL em PASS por alteração de relatório.
> Não remova funcionalidades problemáticas como forma de corrigir bugs.
> Preserve o Hermes original e minimize alterações invasivas no core.
> Após cada correção, rode o teste específico e depois a regressão completa.

Proibido, sobre trabalho existente, sem autorização explícita do usuário:
```
git reset --hard | git clean -fd | git checkout . | git restore . | git stash drop
```
`DO_NOT_PUSH_YET`. Commits **são** exigidos nesta rodada (ver Wave 0) — push, não.

Não revele API keys, tokens, cookies ou credenciais. Redija com `[REDACTED]`.
Não acesse nem envie comandos para servidores remotos.
Não afirme sucesso sem anexar a saída real do comando.

Classifique sempre: `comprovado` · `parcialmente comprovado` · `não comprovado` · `BLOCKED_BY_EXTERNAL_DEPENDENCY` · `defeito confirmado`.

---

## 1. CONTEXTO — o que já foi corrigido (NÃO refaça, NÃO quebre)

Uma auditoria independente (R1) encontrou 4 P0 e 12 P1. Uma rodada de remediação já aconteceu e uma segunda auditoria (R2) **verificou por execução** que os quatro P0 estão fechados. Relatórios completos em `audit/`:

```
audit/HERMES_OMNIROUTE_AUDIT_R2.md          ← LEIA PRIMEIRO (delta e evidências)
audit/HERMES_OMNIROUTE_FINDINGS.md          ← os 41 findings originais, detalhados
audit/HERMES_OMNIROUTE_SECURITY.md
audit/HERMES_OMNIROUTE_ARCHITECTURE.md
audit/HERMES_OMNIROUTE_MCP_MATRIX.md
audit/HERMES_OMNIROUTE_TEST_GAPS.md
audit/HERMES_OMNIROUTE_UX.md
audit/HERMES_OMNIROUTE_IMPROVEMENT_PLAN.md
audit/CODEX_HERMES_OMNIROUTE_FIX_PROMPT.md
```

**Corrigido e verificado — preserve integralmente:**

| Achado | Como foi corrigido |
|---|---|
| Guardrail nunca carregava | `plugin.yaml` com `kind: backend` + `security_critical: true`; scan do namespace Studio por último para impedir shadowing |
| RCE via `OMNIROUTE_PACKAGE_ROOT` | `integrations/omniroute-mcp-policy.mjs`: allowlist + `realpath` + nome/versão do pacote + `dist/**/server.js` compilado (sem `tsx`) |
| Escopos MCP auto-concedidos | `DEFAULT_OMNIROUTE_MCP_SCOPES` = 6 escopos; `write:plugins` removido |
| Renderer → execução local | `security-boundaries.ts` (`resolveAllowedFsIpcPath`, `externalFileBlockReason`) + `fs-ipc.ts` roteado |
| Sem CSP / webview livre | `content-security.ts` + `onHeadersReceived` + `will-attach-webview` + `will-redirect` + `isTrustedRendererNavigation` |
| Endpoint 20128 sem auth | `omniroute-local-auth.ts` — token em `safeStorage`, nunca ao renderer, revogado na desinstalação |
| Escrita no runtime do Hermes original | `resolveStudioManagedPaths` + `HERMES_STUDIO_PLUGIN_ROOT` validado em `get_studio_managed_plugins_dir` |
| Erro de I/O abortava o boot | `installManagedComponents` + IPC `hermes:omniroute:managed:status` |
| Backup prometido e inexistente | `backupManagedDirectory` / `backupManagedFile` em `.omniroute-backups/<snapshot>` |
| Denylist / gate de verificação / raiz de confiança | guardrail reescrito: parser do núcleo, `exit_code` real, `resolve_agent_cwd()` com fail-closed |

**Resultado medido na R2 (reproduza antes de mexer — seção 4):** 18/18 comandos destrutivos bloqueados, 5/5 negativos passando, caminho relativo exigindo aprovação, gate de verificação fail-closed.

---

## 2. O QUE VOCÊ VAI CORRIGIR

### WAVE 0 — URGENTE: a correção de 4 P0 está fora do controle de versão
`R2-NEW-01 · P1`

Estes arquivos **não estão em nenhum commit**:
```
apps/desktop/electron/content-security.ts
apps/desktop/electron/content-security.test.ts
apps/desktop/electron/security-boundaries.ts
apps/desktop/electron/omniroute-local-auth.ts
apps/desktop/electron/omniroute-local-auth.test.ts
apps/desktop/electron/omniroute-security.test.ts
integrations/omniroute-mcp-policy.mjs
```
Um `git clean -fd` apaga a remediação inteira de quatro P0. Nada disso está em diff revisável nem em CI, e não sobrevive a um clone novo.

Além deles há 12 arquivos rastreados modificados e não commitados (`main.ts` +291, `omniroute-mcp-bridge.mjs` +375, `dz23-guardrail/__init__.py` +165, `hermes_cli/plugins.py`, `tools/approval.py`, `fs-ipc.ts`, `bundled-product-studio.ts` e outros).

**Faça, nesta ordem:**
1. Backup primeiro:
   ```powershell
   cd C:\Users\you\Documents\Codex\Hermes-OmniRoute
   git bundle create ..\hermes-r2-backup-$(Get-Date -Format yyyyMMdd-HHmmss).bundle --all
   git diff > ..\hermes-r2-worktree.diff
   git status --porcelain=v1 > ..\hermes-r2-status.txt
   ```
2. `git add` explícito dos arquivos de código acima **e** dos 12 rastreados. Não use `git add -A` (evita arrastar `audit/_raw/*.tar`, `*.tgz`, `__pycache__`).
3. Um commit, mensagem descrevendo a remediação dos P0. **Sem push.**
4. Adicione `audit/_raw/` ao `.gitignore` (são artefatos de trabalho, alguns com centenas de MB).

**Aceite:** `git status` limpo para código; `git log -1 --stat` mostra os 7 arquivos novos + os 12 modificados.

---

### WAVE 1 — a política anula o guard que acabou de ser criado
`R2-NEW-02 · P1`

`tools/approval.py:774-799` ganhou três padrões deliberados, com este comentário:
> *"naming a new package mutates the dependency graph and may immediately execute untrusted lifecycle hooks. Keep this an approvable warning (rather than a hard block) **so the user can inspect the package/version before it runs**"*

E `apps/desktop/src/app/settings/omniroute-preset.ts:81-82` define:
> `smart_policy: 'Auto-approve read-only inspection, tests, builds, **dependency installation**, and reversible writes…'`

O guard leva o comando ao aprovador; o aprovador é um LLM; a política manda aprovar exatamente a categoria que o guard existe para segurar. O usuário nunca vê o nome do pacote.

**Correção:**
1. Remover `dependency installation` da `smart_policy`, ou qualificar para *"instalação a partir de lockfile já declarado no workspace"*.
2. Acrescentar à política, explicitamente: *"Escalate any command that names a new package."*
3. Quando a aprovação for exibida, mostrar **nome e versão do pacote** extraídos do comando.
4. `R2-NEW-08 · P3`: estender os padrões para `uv pip install`, `poetry add`, `pdm add`, `conda install`.

**Teste:** `npm install left-pad` → exige aprovação e a mensagem contém `left-pad`; `npm ci` → auto; `uv pip install requests` → exige aprovação; `pip install -r requirements.txt` → auto.

---

### WAVE 2 — resíduos de segurança

**`R2-NEW-04 · P2` — extensões executáveis incompletas.**
`apps/desktop/electron/security-boundaries.ts:18-30` cobre `.bat .cmd .com .exe .jar .js .lnk .msi .ps1 .scr .vbs`. Faltam vetores clássicos de execução por associação no Windows:
```
.hta .wsf .wsh .jse .vbe .reg .url .scf .pif .cpl .msc .msp .appref-ms .ps2 .psc1 .chm .sct .inf
```
`shell.openPath` num `.hta` executa `mshta.exe`; `.url` e `.scf` disparam navegação/SMB.
**Preferível:** inverter para **allowlist** de extensões seguras para abertura externa.

**`R2-NEW-05 · P2` — seleção nativa pode promover a raiz de um drive.**
`main.ts / approveNativeSelectedPath`:
```ts
nativeApprovedFsRoots.add(path.resolve(directory ? selectedPath : path.dirname(selectedPath)))
```
Se o usuário escolher um arquivo em `C:\`, `path.dirname` devolve `C:\` e o drive inteiro entra em `desktopAllowedFsRoots()` pelo resto da sessão, anulando o confinamento para todo o disco.
**Correção:** recusar raízes iguais ao anchor de um drive ou ao diretório home; para seleção de arquivo, conceder **o arquivo**, não o diretório-pai.

**`R2-NEW-06 · P2` — `frame-src` permite HTTP em texto claro.**
`content-security.ts:9` — `"frame-src 'self' https: http:"`. Restrinja `http:` a `http://127.0.0.1:* http://localhost:*`, como já foi feito corretamente em `connect-src`. Reveja `img-src` e `media-src` com o mesmo critério.

**`R2-NEW-07 · P2` — o fail-closed do plugin crítico é anulado uma camada acima.**
`agent/tool_executor.py` está **intocado** e contém:
```python
except Exception:
    return None      # "sem diretiva de bloqueio" → a ferramenta EXECUTA
```
`hermes_cli/plugins.py` converte exceção **dentro** de um callback crítico em `{"action":"block"}` — correto. Mas qualquer exceção que escape antes do invoke ainda libera a ferramenta.
**Correção:** no `tool_executor`, quando houver ao menos um hook `security_critical` registrado, converter exceção em bloqueio em vez de `None`. Bônus: envolver `from tools.approval import _command_detection_variants` (`plugins/dz23-guardrail/__init__.py:164-166`) em `try/except` que degrade para uma detecção conservadora, nunca para "sem detecção".

---

### WAVE 3 — pt-BR (maior defeito de produto aberto)
`HERMES-017 · P1`

Medição atual: `pt-br.ts` ≈449 chaves contra ≈2.463 de `en.ts` → **18,2%**. `defineLocale` faz merge sobre `en`, então **~82% da interface aparece em inglês** para o público que a própria documentação define como *"nontechnical users"* brasileiros.

**Ordem de tradução, por impacto:**
1. Diálogos de aprovação e mensagens de segurança — inglês aqui é ativamente perigoso: o usuário aprova o que não entendeu.
2. Erros e estados de falha.
3. Onboarding e primeiro run.
4. Configurações (todas as abas).
5. Estados vazios, loading, notificações, tooltips.

**Obrigatório:** teste de cobertura que percorre `Translations` recursivamente, compara as chaves de cada locale com `en` e **falha abaixo de 90%** para locales anunciados como suportados. Enquanto abaixo do limiar, marcar pt-BR como "parcial" no seletor de idioma.

---

### WAVE 4 — testes que reportam PASS sem asserir

**`HERMES-022 · P2`** — 8 sites usam `if (process.platform !== 'win32') { …assert… }` **dentro do corpo** do teste. No Windows executam, não asserem nada e reportam PASS:
```
apps/desktop/electron/desktop-installation.test.ts:42, :56, :74
apps/desktop/electron/fs-read-dir.test.ts:189
apps/desktop/electron/git-review-ops.test.ts:42
apps/desktop/electron/ssh-connection.test.ts:804, :820
apps/desktop/scripts/stage-native-deps.test.mjs:576
```
Converta para `test.skipIf(...)` (que reporta skip honestamente) **e** escreva o equivalente Windows. Adicione regra de lint proibindo `process.platform` dentro de um bloco `test(...)`.

**`HERMES-033 · P2`** — `hardening.test.ts:30` pula 7 testes no Windows (`posixTest`). São exatamente os que provam que `connection.json`, que contém o token remoto, é owner-only. Na única plataforma de release a proteção em repouso é **não verificada**. Implemente e teste endurecimento por ACL (`icacls <arquivo> /inheritance:r /grant:r "%USERNAME%":F`) **lendo a ACL de volta** para asserir.

**`HERMES-012 · P1`** — `ssh-connection.test.ts` tem 9 construtores com `mux: true` injetado para manter os testes exercitando o caminho multiplexado, que **não é o default no Windows**. O caminho real de produção tem zero cobertura. Parametrize a suíte por `mux: [true, false]` em todas as plataformas. E o único teste de ciclo de vida SSH real (`windows-remote-live.test.ts:28`) é `skipIf` sem host — torne-o executável em CI com um container OpenSSH efêmero em vez de depender de um rig manual.

**`HERMES-023 · P2`** — `tests/skills/test_product_studio_skill.py`: todas as assertions são `assert "<frase em inglês>" in <markdown>`. Reduza a um smoke de schema (frontmatter parseável, referências existem no disco, `platforms` correto) e mova o resto para testes de comportamento.

---

### WAVE 5 — produto e consistência

**`HERMES-018 · P2`** — `preview-browser-bar.tsx:188-196`: o chip com ícone de escudo e o texto "Acesso do agente ativo" é **estático**, sem prop nem condição, e some abaixo do breakpoint `lg` (`hidden … lg:flex`). Vincule ao estado real (ligado/desligado/pausado), torne visível em todas as larguras (colapsar para ícone com tooltip, não `hidden`) e adicione `aria-live` para anunciar mudança de estado.

**`HERMES-025 · P2`** — `gateway/slash_commands.py:2859-2866` e `hermes_cli/cli_commands_mixin.py:2994-3009`: o gateway pausa só para `draft`, o CLI pausa para qualquer contrato — e o comentário do CLI afirma o contrário do que o código faz. Ambos usam `mgr.pause(...) or state`: se `pause` retorna `None`, a mensagem ainda afirma "paused for review". Extraia uma função única; propague falha de pausa como erro visível; alinhe o comentário.

**`HERMES-035 · P2`** — `integrations/omniroute-daily-health.py`: `MODELS_URL` é a terceira cópia do literal `127.0.0.1:20128` (as outras em `omniroute-preset.ts:2` e `docs/hermes-omniroute-studio.md:7`) e a contagem de erros soma **cada ocorrência** da palavra na linha, inclusive dentro de conteúdo de usuário. Constante única compartilhada; parse por nível estruturado; no máximo uma contagem por linha; teste com log de fixture.

---

### WAVE 6 — proveniência do release
`R2-NEW-03 · P2`

`resources/install-stamp.json` traz `"dirty": true`. O SHA-256 do instalador confere com o esperado (`e4c822706dcac961616080aa9324bd255bd437015b95d52ad87ad0c73dc67490`) — o artefato é o que se diz que é — mas sua **fonte** não é reproduzível: é `9d80176` mais um delta não versionado.

**Correção:** o script de build de release deve **falhar** quando o worktree estiver sujo, ou carimbar o hash do delta e anexá-lo ao artefato. Depois da Wave 0, refaça o build a partir do commit limpo e registre o novo SHA-256.

---

## 3. GATE DE CORREÇÃO

Na máquina Windows real, com a saída anexada ao relatório:
```
npm run typecheck
npm run lint
npm test
build · NSIS · secret scan · dependency/security scan
```
Mais todos os testes novos das Waves 1–5.

Descubra primeiro os scripts reais em `package.json` / `pyproject.toml`. Não invente comandos se já houver scripts oficiais.

Nenhum gate pode ser declarado `PASS` sem o output do comando anexado.

---

## 4. REPRODUZA A EVIDÊNCIA DA R2 ANTES E DEPOIS

Rode isto **antes** de qualquer alteração (para confirmar o baseline) e **de novo no fim** (para provar que não regrediu). Da raiz do repositório:

```python
# python - <<'PY'
import importlib.util, os, sys, types, re
from pathlib import Path

# stub fiel-o-suficiente do parser do núcleo, para isolar o guardrail
tools = types.ModuleType('tools'); tools.__path__=[]
appr = types.ModuleType('tools.approval')
def _variants(command):
    yield command
    if re.search(r"[A-Za-z]:\\|\\\\", command):
        yield command.replace('\\','/')
appr._command_detection_variants = _variants
sys.modules['tools']=tools; sys.modules['tools.approval']=appr; tools.approval=appr

spec = importlib.util.spec_from_file_location('g','plugins/dz23-guardrail/__init__.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
os.makedirs('/tmp/ws', exist_ok=True) if os.name != 'nt' else os.makedirs(os.path.expandvars(r'%TEMP%\ws'), exist_ok=True)
WS = '/tmp/ws' if os.name != 'nt' else os.path.expandvars(r'%TEMP%\ws')
os.environ['HERMES_GUARDRAIL_WORKSPACE_ROOTS'] = WS

DESTRUTIVOS = ['del /s /q C:\\Users\\you\\Documents','rd /s /q C:\\projeto',
 'Remove-Item -Recurse -Force C:\\Users\\you','rm -r -f /tmp/x','rm --recursive --force /tmp/x',
 'find . -delete','git clean -fdx','git reset --hard','git push --force origin main',
 'DROP DATABASE producao','TRUNCATE TABLE users','docker volume prune -f','docker image prune -a',
 'vssadmin delete shadows /all','reg delete HKLM\\Software\\X /f','takeown /f C:\\ /r',
 'rm -rf /tmp/x','shutil.rmtree("C:/x")']
NEGATIVOS = ['git clean -n','git clean --dry-run','npm ci','ls -la','echo "rm -rf /" >> notas.txt']

b = sum(bool((r:=m.on_pre_tool_call('terminal',{'command':c})) and r.get('action')=='block') for c in DESTRUTIVOS)
fp = sum(bool((r:=m.on_pre_tool_call('terminal',{'command':c})) and r.get('action')=='block') for c in NEGATIVOS)
print(f"destrutivos bloqueados: {b}/{len(DESTRUTIVOS)}   (esperado {len(DESTRUTIVOS)}/{len(DESTRUTIVOS)})")
print(f"falsos positivos:       {fp}/{len(NEGATIVOS)}   (esperado 0)")

for p in ['../../../../home/user/.ssh/authorized_keys','./../../etc/passwd']:
    r = m.on_pre_tool_call('write_file', {'path': p})
    print(f"relativo {p!r:50} -> {(r or {}).get('action','None')}   (esperado approve)")

def gate(s, cmd, result, status='success'):
    m.on_post_tool_call('write_file', {'path': os.path.join(WS,'a.ts')}, {'ok':True}, 'success', s)
    if cmd: m.on_post_tool_call('terminal', {'command':cmd}, result, status, s)
    return m.on_pre_verify(session_id=s, coding=True, changed_paths=[os.path.join(WS,'a.ts')])

for label, cmd, res, esperado in [
    ('echo npm test','echo npm test','npm test','EXIGE'),
    ('npm test falhou (string)','npm test','5 tests failed','EXIGE'),
    ('npm test exit_code=1','npm test',{'exit_code':1},'EXIGE'),
    ('npm test exit_code=0','npm test',{'exit_code':0},'satisfeito'),
    ('pytest exit_code=0','pytest',{'exit_code':0},'satisfeito'),
    ('sem exit_code','npm test',{'ok':True},'EXIGE')]:
    got = 'EXIGE' if gate('s-'+label, cmd, res) else 'satisfeito'
    print(f"gate {label:28} -> {got:11} (esperado {esperado})", '' if got==esperado else '  ** REGRESSAO **')

print('doc citando rm -rf ->', m.on_pre_tool_call('write_file', {'path': os.path.join(WS,'d.md'),'content':'Nunca rode rm -rf /'}), '(esperado None)')
PY
```

**Baseline medido na R2:** `18/18` destrutivos, `0/5` falsos positivos, `approve` nos relativos, gate correto nos 6 casos, `None` na documentação. **Qualquer número diferente disso no fim é regressão e deve ser tratado como defeito confirmado.**

---

## 5. AUDITORIA INDEPENDENTE PÓS-CORREÇÃO (obrigatória)

Terminadas as correções e o gate, **troque de papel**: você agora é o auditor independente, e o autor das correções é um terceiro em quem você não confia. Não confie no seu próprio relatório de implementação, nos nomes de função, nos comentários nem nos testes existentes.

### 5.1 Reancoragem obrigatória
Registre, com saída real: diretório atual, raiz do Git, branch, commit, `git status` completo, arquivos modificados e não rastreados, SHA-256 do instalador, SHA-256 do executável instalado, e `resources/install-stamp.json` (incluindo `dirty`). Compare byte a byte os componentes gerenciados em `resources/` com o worktree — **é assim que se descobre se a build corresponde à fonte.**

### 5.2 Regra que gerou os melhores achados nas rodadas anteriores
Saída vazia **não é** evidência de nada. Vários comandos `git` nesse repositório estouram timeout e devolvem vazio, que se lê como "limpo". **Sempre cheque o exit code.** Um `git diff --stat` que retorna vazio por timeout foi, nas duas auditorias anteriores, o erro mais fácil de cometer.

### 5.3 Pergunte-se, nesta ordem
1. Se eu quisesse quebrar este aplicativo agora, qual caminho eu tentaria?
2. Que problema não seria detectado pela suíte de testes atual?
3. Qual integração está sendo considerada pronta apenas porque inicializou?
4. Qual guardrail existe na UI mas não no ponto real de execução?
5. Um renderer comprometido alcança filesystem, shell, MCP ou SSH?
6. Conteúdo malicioso vindo de web, arquivo, memória ou MCP induz operação privilegiada?
7. O aplicativo se recupera de falhas ou só funciona no happy path?
8. Alguma correção desta rodada declara uma propriedade que o runtime não implementa? *(foi assim que se descobriu `security_critical` decorativo e a promessa de backup inexistente)*

### 5.4 O que as auditorias anteriores NÃO conseguiram fazer — e você consegue
Isto é o maior valor que você pode acrescentar. Tudo abaixo está `NOT_TESTED` até hoje:

- **Rodar os gates de verdade** no Windows: typecheck, lint, os ~1.549 testes Electron, build, NSIS, secret scan. Publique a **lista nomeada dos testes pulados com o motivo** — a R1 identificou 11 de 12 estaticamente e o 12º continua desconhecido.
- **Resolver 106 × 107 ferramentas MCP:** suba o servidor e faça `tools/list`. O servidor já calcula `TOTAL_MCP_TOOL_COUNT` via `countUniqueMcpTools` (`server.ts:104-117`) — use a fonte, e passe a gerar o número da documentação em build.
- **Caveman de verdade:** ligar/desligar e comprovar que o estado mudou **no OmniRoute**, não só a aparência do switch. Teste `omniroute_compression_status` e `omniroute_set_compression_engine` com `caveman` e `off`; teste 401, 403, 404, timeout e OmniRoute desligado; confirme rollback quando a alteração falha; **restaure o estado original ao final**.
- **Escopos MCP no runtime:** com o default de 6 escopos, chamar `plugin_install` deve retornar `isError` com `missing_scopes`. Prove.
- **Início frio** com a tela "Modelo" aberta antes do backend pronto: a UI não pode ficar presa em erro de 15s; `model/info`, `model/options`, `model/auxiliary`, `model/moa` precisam de política coerente de timeout; troca de perfil não pode misturar resultados assíncronos.
- **Aplicativo real:** startup, onboarding, navegação, Product Studio, Memory, Agents, Goal, MCP, Preview, SSH, Guardrails, Cron, pt-BR, settings, restart, shutdown, recuperação de erro. Inspecione console, network, logs do Electron, processos, uncaught exceptions e unhandled rejections. **Zero processos órfãos** após fechar (preview, node do bridge, PTY).
- **Guardrail visível:** confirme na UI que o guardrail aparece como ativo e que `del /s /q` é realmente bloqueado numa sessão real de agente.
- **pt-BR na tela:** selecione Português (Brasil), **reinicie**, e percorra início, conversas, agentes, configurações, Modelo, Aparência, Segurança, Memória e Contexto, Provedores, Contas, Chaves de API, Endpoints personalizados, Gateways, Ferramentas, Plugins, menus, diálogos, tooltips, estados vazios e mensagens de erro. Liste **cada** texto em inglês com tela, texto, arquivo de origem e classificação: *marca/nome técnico* ou *tradução ausente*. Nomes oficiais de produtos e modelos não contam como falha.
- **Performance:** `COLD_START`, `WARM_START`, `IDLE_RAM`, `ACTIVE_RAM`, `IDLE_CPU`, `ACTIVE_CPU`, `PROCESS_COUNT`, `MCP_LATENCY`, `PREVIEW_START_TIME`, `SHUTDOWN_TIME`. Procure crescimento progressivo de memória em 30 min. Se não medir, escreva `NOT_MEASURED` — não invente número.
- **Instalador:** instalação limpa, upgrade, reinstalação, atalhos, diretórios, dados persistentes, desinstalação, arquivos residuais, permissões, comportamento com o app aberto, rollback após falha. **Use uma VM ou usuário Windows separado — não desinstale a instalação principal do usuário.**
- **Injeção de falha:** MCP indisponível, tool com erro, timeout, rede caindo, preview morto, SSH falhando, memória indisponível, config corrompida, porta ocupada, restart no meio da operação. Em cada caso o sistema deve reportar `FAILED` ou `BLOCKED` — **nunca sucesso aparente**.

### 5.5 Classificação de findings
`P0` RCE, perda de dados, segredo exposto, bypass grave · `P1` funcionalidade crítica quebrada, integração falsa, guardrail contornável, race séria · `P2` UX importante, recovery incompleto, performance, cobertura ausente · `P3` refatoração, visual, documentação.
Não aumente severidade artificialmente. Cada finding precisa de: `ID · Severidade · Componente · Arquivo · Linha/função · Sintoma · Causa raiz · Reprodução · Impacto · Evidência · Correção · Teste de regressão`. Separe **FACT** de **HYPOTHESIS**. Não invente evidência.

### 5.6 Entregável da auditoria
Crie `audit/HERMES_OMNIROUTE_AUDIT_R3.md`, untracked ou em commit separado do código, contendo:
1. Estado reancorado com todas as saídas reais.
2. Tabela **corrigido / ainda aberto / novo** contra os IDs `HERMES-*` e `R2-NEW-*` deste documento — cada linha com evidência.
3. Resultado do script da seção 4, antes e depois.
4. Findings novos no formato de 5.5.
5. Matriz das 106/107 ferramentas MCP com resultado **vivo**, não estático.
6. Lista completa dos textos em inglês encontrados no passeio pt-BR.
7. Baseline de performance ou `NOT_MEASURED` justificado.
8. Quadro final:
```text
VERDICT=<APPROVED_FOR_RELEASE_PREP|APPROVED_WITH_FINDINGS|REQUIRES_CORRECTIONS|CRITICAL_BLOCKER>
P0_ABERTOS= P1_ABERTOS= P2_ABERTOS= P3_ABERTOS=
GUARDRAIL_REEXECUTION=<X/18 destrutivos, Y/5 falsos positivos>
TYPECHECK= LINT= UNIT= ELECTRON= BUILD= NSIS= SECRET_SCAN=
ELECTRON_TESTS_PASS= FAIL= SKIPPED= SKIPPED_NAMED=<sim|não>
MCP_TOOLS_DISCOVERED= MCP_PASS= MCP_FAIL= MCP_BLOCKED= MCP_NOT_TESTED=
CAVEMAN_STATE_CHANGE_PROVEN=<sim|não>
PT_BR_COVERAGE=<%>
APP_RUNTIME_TESTED=<sim|não>  ORPHAN_PROCESSES=<0|N>
INSTALLER_SHA256= INSTALL_STAMP_DIRTY=<true|false>
GIT_COMMIT_CREATED=<sim|não>  GIT_PUSH_PERFORMED=NO
```

### 5.7 Se discordar de algum finding
```text
DISPUTED_FINDING
id=  motivo=  evidência=
```
Não implemente correção incorreta apenas porque o relatório mandou. Os findings anteriores são hipóteses técnicas de alta prioridade, não verdade absoluta — reproduza antes de corrigir.

### 5.8 Se não puder comprovar
```text
BLOCKED_BY_EXTERNAL_DEPENDENCY
dependency=  affected_feature=  what_was_verified=
what_could_not_be_verified=  exact_requirement_to_unblock=
```
**Não use mocks para converter esse estado em PASS.**

---

## 6. LOOP

```
IMPLEMENT → TEST → INSPECT → FIND REGRESSION → FIX ROOT CAUSE → RETEST
```
Repita até não existirem falhas internas conhecidas corrigíveis dentro do escopo. Não há limite de uma rodada.

---

## 7. NÃO REMOVA NEM ENFRAQUEÇA

`contextIsolation: true`, `sandbox: true`, `nodeIntegration: false` em todas as janelas · `setWindowOpenHandler` com `deny` incondicional · preload com API nominal, sem passthrough de canal · `execFile` com argv em array, sem `shell: true` · `resolveReadableFileForIpc` + `rejectSensitiveFilePath` · CDP fechado em build empacotado · `safeStorage` para tokens · **hardline floor** aplicado antes do `--yolo` · isolamento de canal do `_smart_approve` (política no system, comando em `<command>`) · `execute_code` em subprocesso com RPC autenticado · gate não-bypassável de escrita em `AGENTS.md`/`CLAUDE.md`/`.cursorrules` · `request_tool_approval` fail-closed sem humano · identidade lado-a-lado do Studio (appId, executableName, protocolo `hermes-omniroute`, versão PE) · **e toda a remediação R2 listada na seção 1**.

---

## 8. LEMBRETE

Este produto passou em ~1.549 testes enquanto seu plugin de segurança não carregava e seus três gates eram contornáveis por `del /s /q`, por `../` e por `echo`. A rodada de correção resolveu isso de verdade — e mesmo assim deixou a correção inteira fora do controle de versão e uma política que anula o guard recém-criado.

**Teste passando não é funcionalidade. Correção não commitada não é correção.**
