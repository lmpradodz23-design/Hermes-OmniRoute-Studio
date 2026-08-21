# HERMES OMNIROUTE — SEGURANÇA E ATTACK SURFACE

## 1. O que está bem feito (FATO — registrar para não ser destruído)

Antes das lacunas, o que o Codex **não deve** enfraquecer:

- `contextIsolation: true`, `sandbox: true`, `nodeIntegration: false` em **todas as 12 janelas** (`session-windows.ts:46-57` e demais).
- `setWindowOpenHandler` retorna `action: 'deny'` incondicionalmente — `window.open` não abre janela com Node (`main.ts:10959-10963`).
- Preload expõe **funções nomeadas**, sem passthrough genérico `invoke(channel, …)`. Não existe canal dinâmico controlado pelo renderer.
- Nenhum `exec()` nem `shell: true` com string do renderer. Todo o código git/gh/ssh usa `execFile` com argv em array.
- `resolveReadableFileForIpc` (`hardening.ts:467-514`) aplica `rejectSensitiveFilePath`, bloqueando `.ssh/`, `.gnupg/`, `.aws/credentials`, `.env`, `id_rsa`, `.pem/.p12/.pfx/.kdbx`, `.npmrc/.netrc/.pypirc`, com cap de bytes e checagem de realpath.
- CDP remoto fechado em build empacotado (`dev-cdp.ts:58-60`).
- Tokens por `safeStorage` + arquivos 0600 em POSIX.
- **Hardline floor** de comandos aplicado **antes** do bypass `--yolo` (`tools/approval.py:4365-4368` vs `:4393`), com 12 regras e detecção resistente a ofuscação por quoting/`$()`/backtick (`_command_detection_variants`, `:2224`).
- `_smart_approve` isola corretamente a política do operador no canal system e envolve o comando em `<command>`, removendo comentários de shell antes (`:3261-3383`). É o único ponto do produto que trata separação de canal de confiança com rigor.
- `execute_code` roda em **subprocesso** com RPC autenticado por token e socket 0600 (`tools/code_execution_tool.py:1514-1523`) — não no processo do agente. Consequência positiva: `os.chdir` do código do agente **não** afeta o processo pai.
- Escrita em arquivos de instrução (`AGENTS.md`, `CLAUDE.md`, `.cursorrules`) tem gate não-bypassável por yolo em `tools/file_tools.py:839-880`.
- `request_tool_approval` é **fail-closed** quando não há canal humano (`approval.py:3878`, `:3519-3542`).

## 2. Attack surface map

```text
ENTRY_POINT | TRUST | REACHABLE | CAPABILITY | GUARDRAIL | BYPASS | IMPACT | STATUS
```

| Entry point | Trust | Componente alcançável | Capacidade | Guardrail existente | Bypass possível | Impacto | Status |
|---|---|---|---|---|---|---|---|
| Página web → renderer | NÃO CONFIÁVEL | Renderer principal | DOM, todo `window.hermesDesktop` | **nenhuma CSP** | XSS direto | 165 canais IPC | **ABERTO** (HERMES-013) |
| Renderer → `hermes:fs:writeText` | SEMI | Filesystem | escrever ≤1MB em qualquer path | comentário afirma raiz, não há | — | escrita arbitrária | **ABERTO** (HERMES-004) |
| Renderer → `openExternal('file://…')` | SEMI | `shell.openPath` | executar com associação do SO | allowlist de esquema **depois** do ramo file | ramo `file:` | **execução local** | **ABERTO** (HERMES-004) |
| Renderer → `terminal.start`+`write` | SEMI | PTY | comando arbitrário | por design | — | shell do usuário | ACEITO por design |
| Renderer → `<webview>` | SEMI | novo WebContents | atributos do DOM | **sem `will-attach-webview`** | `nodeintegration` injetado | Node no guest | **ABERTO** (HERMES-013) |
| Renderer → `fetchLinkTitle` | SEMI | `spawn('curl', …)` | argv sem `--` | validação só de string não-vazia | `--config`, `file://` | SSRF / leitura local | **ABERTO** (HERMES-029) |
| Renderer → `updates.branch.set` | SEMI | `git pull` | escolher branch de código executado | nenhuma | — | código não previsto | **ABERTO** (HERMES-034) |
| Modelo → `terminal` | NÃO CONFIÁVEL | shell | comando arbitrário | hardline + approval + guardrail | guardrail inerte; `npm install` sem gate | destruição / supply chain | **PARCIAL** (HERMES-001, 005, 011) |
| Modelo → `file_tools` | NÃO CONFIÁVEL | filesystem | escrita | guardrail outside-workspace | caminho relativo; cwd amplo | escrita fora do escopo | **ABERTO** (HERMES-007, 008) |
| Modelo → MCP (106 tools) | NÃO CONFIÁVEL | OmniRoute | plugins, memória, obsidian, notion, web, skills | escopos "enforced" auto-concedidos | é o próprio design | execução de código via `plugin_install` / `skills_install` | **ABERTO** (HERMES-003) |
| Modelo → SSH | NÃO CONFIÁVEL | host remoto | comando remoto | `shq()`, `--`, perfis | caminho Windows sem cobertura | ação em servidor | **PARCIAL** (HERMES-012) |
| Web → `omniroute_web_fetch` → agente | NÃO CONFIÁVEL | contexto do modelo | instruções indiretas | **nenhuma** marcação de origem | — | prompt injection | **ABERTO** (TB5) |
| GitHub → `github_skills_install` → agente | NÃO CONFIÁVEL | comportamento do agente | instruções persistentes | `write:skills` concedido | — | injeção persistente | **ABERTO** |
| Arquivo do projeto → agente | NÃO CONFIÁVEL | contexto | instruções | `AGENTS.md` tem gate de **escrita**, não de **leitura** | — | prompt injection | **ABERTO** |
| Memória → agente | NÃO CONFIÁVEL | contexto | instruções persistentes | `write:memory` concedido | — | injeção entre sessões | **ABERTO** |
| Env `OMNIROUTE_PACKAGE_ROOT` | NÃO CONFIÁVEL | bridge Node | `import()` de código | nenhuma | — | **RCE** | **ABERTO** (HERMES-002) |
| `%APPDATA%\npm\node_modules\omniroute` | SEMI (gravável pelo usuário) | bridge Node | idem | nenhuma verificação de integridade | — | persistência + execução | **ABERTO** (HERMES-002) |
| Porta local 20128 | NÃO CONFIÁVEL | roteamento de modelos | recebe todo prompt, devolve completion | nenhuma auth, nenhuma identidade | squatting de porta | exfiltração + envenenamento | **ABERTO** (HERMES-016) |
| Cron `omniroute-daily-health.py` | SEMI | HTTP local + logs | leitura | — | — | baixo | OK |

## 3. Cadeias `untrusted input → agent → tool → privileged operation`

Priorizadas conforme a missão exige.

### Cadeia 1 — a mais curta e a mais grave
```text
web_fetch/arquivo/memória (conteúdo hostil)
  → agente é instruído a "instalar uma dependência do projeto"
  → npm install <pacote-malicioso>
  → nenhum padrão em DANGEROUS_PATTERNS → retorna approved ANTES do smart
  → postinstall executa
```
Nenhum gate em nenhum ponto. `smart_policy` não é consultada porque o comando nunca chega ao LLM. HERMES-011.

### Cadeia 2 — via MCP, contornando o Hermes inteiro
```text
conteúdo hostil → agente chama plugin_install (MCP)
  → escopo write:plugins concedido por default (HERMES-003)
  → o dz23-guardrail não intercepta chamadas MCP nem carregaria (HERMES-001)
  → plugin instalado e ativado = execução de código
```

### Cadeia 3 — persistência
```text
conteúdo hostil → omniroute_github_skills_install (write:skills concedido)
  → skill de terceiro em disco
  → o agente carrega e SEGUE aquelas instruções em sessões futuras
  → omniroute_skills_execute (execute:skills concedido)
```

### Cadeia 4 — escrita fora do escopo
```text
conteúdo hostil → agente escreve em "../../../../.ssh/authorized_keys"
  → _outside_workspace retorna False para path relativo (PROVADO)
  → nenhuma aprovação solicitada
```

### Cadeia 5 — renderer comprometido
```text
sem CSP → XSS no renderer
  → hermesDesktop.writeTextFile(<Startup>\a.bat, payload)
  → hermesDesktop.openExternal('file:///…/a.bat')
  → execução local
```
HYPOTHESIS quanto à exploração; FACT quanto a cada primitiva.

## 4. Resistência a prompt injection — avaliação

```text
PROMPT_INJECTION_RESISTANCE = FAIL
```

Razões:
1. **Nenhuma marcação de origem.** Conteúdo de web, arquivo, memória, resposta MCP e skill instalada chega ao modelo indistinguível da instrução do usuário. O produto sabe fazer isso — `_smart_approve` faz exatamente essa separação para o comando — mas não aplica no pipeline principal.
2. **Guardrail inerte** (HERMES-001) remove a única barreira determinística específica do Studio.
3. **Escopos MCP auto-concedidos** (HERMES-003) dão ao agente induzido acesso a instalação de plugin, escrita de memória, filesystem via Obsidian/corpus e rede via proxy.
4. **Instalação de dependência sem gate** (HERMES-011) é o payload mais conveniente possível.
5. **Aprovação `smart` delegada a um LLM** com política em linguagem natural — mesmo bem isolada, é uma barreira probabilística, não determinística, e só é consultada quando um regex já marcou o comando.

O que **funciona** e deve ser preservado: hardline floor antes do yolo; fail-closed do `request_tool_approval` sem humano; isolamento de canal no `_smart_approve`; gate não-bypassável de escrita em arquivos de instrução.

## 5. Segredos

```text
SECRET_SCAN (58 arquivos staged) = PASS
```
Nenhum literal de credencial: nenhum `sk-…`, `ghp_…`, `AKIA…`, `xox[bapr]-…`, nenhum `BEGIN PRIVATE KEY`, nenhum caminho absoluto de usuário hardcoded nos arquivos novos. `XIAOMI_API_KEY` mantém `password: True` no prompt de config.

Pontos de atenção que **não** são exposição atual, mas são risco de manuseio:
- `_redact` fail-open (HERMES-020) → relatório pode ir ao disco sem redação.
- Relatórios de tarefa em `<HERMES_HOME>/task-reports/` sem endurecimento de permissão.
- `connection.json` sem verificação de proteção no Windows (HERMES-033).
- `omniRouteMcp.getConfig()` devolve ao renderer o caminho absoluto do node e do bridge — informação de reconhecimento, não segredo.
- Prompt completo trafega em texto claro para 127.0.0.1:20128 sem autenticação (HERMES-016).

Nenhum segredo é reproduzido neste relatório. Onde seria necessário: `[REDACTED]`.
