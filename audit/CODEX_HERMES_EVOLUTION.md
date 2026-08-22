# CODEX — EVOLUÇÃO DO HERMES OMNIROUTE STUDIO
## 9 capacidades novas + workspace no padrão Qoder/Quest

> Documento autossuficiente. Leia inteiro antes de tocar em qualquer arquivo.
> Projeto: `C:\Users\zodyp\Documents\Codex\Hermes-OmniRoute`
> Branch: `feature/hermes-omniroute-studio`

---

## 0. PRÉ-REQUISITO OBRIGATÓRIO

**Execute `audit/CODEX_R2_FIX_AND_REAUDIT.md` primeiro, até o fim da Wave 0 no mínimo.**

Motivo: a remediação de quatro P0 (`content-security.ts`, `security-boundaries.ts`, `omniroute-local-auth.ts`, `omniroute-mcp-policy.mjs` e seus testes) ainda está **untracked**. Construir novas features sobre código não versionado significa que um `git clean -fd` apaga a base junto com o novo trabalho.

Se a Wave 0 já foi feita e `git log -1 --stat` mostra esses arquivos, prossiga.

---

## 1. REGRAS INEGOCIÁVEIS

> Corrija e construa na causa raiz. Não esconda problemas para obter pipeline verde.
> Não remova testes para fazê-los passar. Não enfraqueça assertions.
> Não substitua integrações reais por mocks para declarar sucesso.
> Não remova funcionalidade problemática como forma de corrigir bug.
> Preserve o Hermes original e minimize alterações invasivas no core.
> Após cada entrega, rode o teste específico e depois a regressão completa.
> Não afirme sucesso sem anexar a saída real do comando.

`DO_NOT_PUSH_YET`. Commits por entrega, sim. Proibido `git reset --hard`, `git clean -fd`, `git checkout .`, `git restore .`, `git stash drop` sobre trabalho existente.

Classifique sempre: `comprovado` · `parcialmente comprovado` · `não comprovado` · `BLOCKED_BY_EXTERNAL_DEPENDENCY`.

**Princípio que governa todo este documento:** o Hermes já tem quase tudo que essas features precisam. Nenhuma entrega abaixo deve reimplementar um mecanismo existente. Onde eu digo "use o hook X em `arquivo:linha`", é porque verifiquei que ele existe e é chamado.

---

## 2. MAPA DO QUE JÁ EXISTE (não reimplemente)

Verificado em auditoria. Use estes pontos de extensão:

```
HOOKS (hermes_cli/plugins.py:161-390 = VALID_HOOKS; register em :3114)
  on_session_start   → agent/conversation_loop.py:987
  pre_tool_call      → agent/tool_executor.py:624-651
  post_tool_call     → via model_tools (_emit_post_tool_call_hook)
  pre_verify         → agent/conversation_loop.py:8195-8236
  post_api_request   → agent/conversation_loop.py:6692-6727
  subagent_stop      → tools/delegate_tool.py:3453-3466
  on_session_end     → agent/turn_finalizer.py:813-831

APROVAÇÃO (tools/approval.py)
  check_all_command_guards   :4342-4985   ordem: hardline → sudo → deny → yolo/off →
                                          allowlist → não-interativo → dangerous → smart → humano
  detect_hardline_command    :601-621     piso não-bypassável, aplicado ANTES do yolo (:4365)
  _smart_approve             :3322-3413   isolamento de canal: política no system, comando em <command>
  request_tool_approval      :3794-3884   fail-closed sem humano; rule_key vira allowlist persistente
  DANGEROUS_PATTERNS         :774+        já cobre instalação de pacote novo

GUARDRAIL (plugins/dz23-guardrail/__init__.py) — kind: backend, security_critical: true
  _workspace_roots / _outside_workspace / _resolved_candidate
  _destructive_match (usa tools.approval._command_detection_variants)
  _verification_exit_code (exige exit_code inteiro real)
  _write_task_report / _redact / _git_summary

WORKSPACE   agent/runtime_cwd.py:60  resolve_agent_cwd()
SEGURANÇA   apps/desktop/electron/security-boundaries.ts (DEFAULT_OMNIROUTE_MCP_SCOPES,
            resolveAllowedFsIpcPath, externalFileBlockReason)
            apps/desktop/electron/content-security.ts (CSP, hardenWebviewAttachment,
            isTrustedRendererNavigation)
            apps/desktop/electron/omniroute-local-auth.ts (token safeStorage)
GOAL        gateway/slash_commands.py + hermes_cli/cli_commands_mixin.py
            estado paused/awaiting-spec-review já implementado
MCP         106 ferramentas; escopo default = 6 (security-boundaries.ts)
            omniroute_set_budget_guard, omniroute_cost_report, omniroute_route_request
UI          apps/desktop/src/app/**  · preload.ts (contextBridge, API nominal)
            i18n: en.ts / pt-br.ts / types.ts / catalog.ts / languages.ts
```

---

## 3. AS NOVE CAPACIDADES

### F1 — Aprovação por proveniência (taint tracking)  ★ PRIORIDADE MÁXIMA

**Problema.** `PROMPT_INJECTION_RESISTANCE=FAIL` é o único veredito de segurança que continua aberto. Conteúdo vindo de web, arquivo externo, memória ou resposta MCP chega ao modelo indistinguível da instrução do usuário. Nenhuma correção até hoje tocou nisso.

**Ideia.** O sistema já sabe *quando* conteúdo externo entrou (o `post_tool_call` dispara depois de cada leitura) e já sabe *quando* uma operação privilegiada é proposta (o `pre_tool_call` dispara antes de cada execução). Falta ligar as duas coisas: **escalar a aprovação quando uma operação privilegiada é proposta logo após entrada de conteúdo não confiável.**

Isso é determinístico, não depende de LLM, e mata a classe inteira de injeção indireta.

**Onde implementar.** Inteiramente dentro de `plugins/dz23-guardrail/__init__.py`. **Não altere o core** — os dois hooks já estão registrados e o plugin já é `security_critical`.

**Contrato de dados.**
```python
@dataclass(frozen=True)
class TaintMark:
    source: str        # "web" | "external-file" | "memory" | "mcp-external" | "installed-skill"
    detail: str        # URL, caminho ou nome da ferramenta — redigido antes de log
    tool: str          # ferramenta que trouxe o conteúdo
    turn: int          # contador de turnos da sessão
    at: str            # ISO-8601 UTC
```
Estado por sessão: `Dict[str, Deque[TaintMark]]`, sob o `_state_lock` que já existe.

**Fontes que marcam taint** (em `on_post_tool_call`, quando `_is_success`):
```
web             omniroute_web_fetch · omniroute_web_search · omniroute_oneproxy_fetch
                fetch_link_title · qualquer navegação de browser/preview
external-file   file read cujo caminho resolvido cai FORA de _workspace_roots()
                local_corpus_read · obsidian_read_note · notion_get_page · notion_query_database
memory          omniroute_memory_search · recall de memória nativa do Hermes
mcp-external    qualquer resposta de ferramenta MCP de serviço externo
installed-skill omniroute_github_skills_install · omniroute_skills_execute
```
**NÃO marcam taint:** leitura de arquivo **dentro** do workspace, saída de terminal de comando do próprio usuário, resultado de teste. Marcar tudo tornaria o recurso inútil.

**Operações privilegiadas** que consultam o taint (em `on_pre_tool_call`):
```
instalação de dependência       (o padrão já existe em tools/approval.py:774+)
escrita fora do workspace       (a checagem já existe no guardrail)
qualquer comando via terminal / execute_code que não seja de verificação
SSH / conexão remota
egresso de rede (curl, wget, Invoke-WebRequest, requests)
git push / git remote add
leitura de caminho sensível (rejectSensitiveFilePath já define a lista)
plugin_install · plugin_activate · omniroute_skills_enable · write:memory
```

**Regra de decisão.**
```python
JANELA_TURNOS = 3          # configurável: guardrail.taint_window_turns
if operacao_privilegiada and taint_ativo_dentro_da_janela:
    return {
        "action": "approve",
        "message": (
            f"Esta operação foi proposta {n} turno(s) após a leitura de conteúdo externo "
            f"({marca.source}: {detalhe_redigido}). Confirme que é intenção sua."
        ),
        "rule_key": f"dz23-guardrail:tainted:{tool_name}:{marca.source}",
    }
```
O taint **decai** ao fim da janela, e é **limpo** quando o usuário envia uma nova mensagem (novo turno de usuário = nova intenção declarada). Registre a limpeza em `on_session_start` e num contador de turno alimentado por `post_api_request`.

**Regras que não podem ser violadas:**
- Nunca coloque conteúdo tainted no `smart_policy` nem em canal system — preserve o isolamento de `_smart_approve:3366-3383`.
- A mensagem de aprovação deve dizer **qual fonte** e **quantos turnos atrás**. Sem isso o usuário aprova no automático e o recurso vira ruído.
- `rule_key` com granularidade por `(ferramenta, fonte)` — nunca por diretório-pai, para não repetir o problema de auto-aprovação ampla.
- Se o rastreamento de taint falhar por exceção, **escale** (fail-closed). Nunca degrade para "sem taint".

**Configuração** (`config.yaml`, com defaults seguros):
```yaml
guardrail:
  taint_window_turns: 3
  taint_sources: [web, external-file, memory, mcp-external, installed-skill]
  taint_escalation: approve          # approve | block | off  (off exige confirmação do usuário na UI)
```

**Testes de aceite:**
1. `web_fetch` → 1 turno depois `npm install pacote` → **exige aprovação**, mensagem cita `web` e a URL.
2. `web_fetch` → 5 turnos depois `npm install pacote` → comportamento normal (fora da janela).
3. Leitura de arquivo **dentro** do workspace → `npm install` → **não** escala por taint.
4. `omniroute_memory_search` → escrita fora do workspace → **exige aprovação**, cita `memory`.
5. Mensagem nova do usuário limpa o taint.
6. Exceção no rastreamento → escala, não libera.
7. Nenhum conteúdo tainted aparece no prompt de `_smart_approve`.

**Superfície de UI** (integra com F9 e U1): quando houver taint ativo, o composer mostra um indicador discreto — *"contexto externo ativo · 2 turnos"* — clicável para ver a origem.

---

### F2 — Gravação e replay de sessão

**Problema.** As auditorias mostraram testes que verificam Markdown, testes que confirmam um denylist contra si mesmo e um teste que contorna o loader. A suíte não prova comportamento porque não existe fixture de comportamento real.

**Entrega.** Um gravador que persiste cada sessão como fixture reproduzível, e um replayer que a re-executa.

**Formato** — JSONL append-only em `<HERMES_HOME>/session-recordings/<session-id>.jsonl`:
```json
{"t":"turn_start","turn":4,"at":"...","user_message_sha256":"..."}
{"t":"tool_call","turn":4,"tool":"terminal","args_sha256":"...","args_redacted":{...},
 "taint":[{"source":"web","turn":3}],"approval":{"verdict":"approved","path":"smart"}}
{"t":"tool_result","turn":4,"tool":"terminal","exit_code":0,"result_sha256":"...","duration_ms":812}
{"t":"api_request","turn":4,"provider":"omniroute","model":"auto/coding",
 "usage":{"input_tokens":1200,"output_tokens":340},"cost_usd":0.0031}
{"t":"turn_end","turn":4,"outcome":"completed"}
```
- Argumentos e resultados passam por `_redact` **antes** de gravar. Sem redator disponível → **não grava** (fail-closed, mesma regra do relatório de tarefa).
- Hashes permitem detectar divergência sem armazenar o conteúdo.
- Opt-in por config `recording.enabled`, com retenção configurável e limpeza automática.

**Replay** — `hermes replay <session-id> [--against-model X] [--assert-tools] [--assert-approvals]`:
- re-executa a sequência de decisões contra um runtime atual;
- `--assert-tools` falha se a sequência de ferramentas divergir;
- `--assert-approvals` falha se um veredito de aprovação mudar de `approved` para `denied` ou vice-versa;
- `--against-model` compara duas rotas (ex.: `auto/coding` × preset MoA) e imprime o diff de decisões.

**Gerador de teste** — `hermes replay <id> --emit-test > tests/replay/test_<slug>.py`, produzindo um teste que assere a sequência de ferramentas e os vereditos de aprovação. **Este é o mecanismo que transforma uso real em regressão.**

**Testes de aceite:** gravar uma sessão real com 3 ferramentas; replay reproduz a mesma sequência; alterar um padrão do guardrail e o replay **falha** apontando o veredito divergente; sessão com segredo no argumento grava redigido; `_redact` indisponível → nada gravado.

---

### F3 — Fuzzer de guardrail

**Problema.** O denylist destrutivo passou de 1/12 para 18/18 — mas só porque uma auditoria externa gerou as variantes à mão. Nada no projeto gera essas variantes sozinho.

**Entrega.** `tests/plugins/test_dz23_guardrail_fuzz.py`, parametrizado, que para cada comando destrutivo base gera e assere bloqueio em:
```
aspas simples e duplas · escape com barra invertida
$( ) e crase · encadeamento com ; && || |
separadores \n e \r\n
barra invertida × barra normal em caminhos Windows
opções separadas (-r -f) e combinadas (-rf) e longas (--recursive --force)
espaços múltiplos e tabulação
maiúsculas/minúsculas alternadas
caminho UNC \\servidor\share
prefixo com env var (FOO=1 comando)
prefixo com cmd /c e powershell -Command
```
E um conjunto de **negativos que não podem bloquear**: `git clean -n`, `git clean --dry-run`, `npm ci`, `pip install -r req.txt`, arquivo de documentação citando comandos destrutivos, migração SQL com `DROP TABLE` comentado.

Rode também contra `_VERIFY_PATTERN`: `echo npm test` e variantes **não** podem satisfazer o gate; `pytest`, `python -m pytest`, `uv run pytest`, `npm run test` **devem**.

**Aceite:** o fuzzer falha se qualquer variante escapar. Rode-o no CI em toda alteração de `_DESTRUCTIVE_PATTERNS` ou `_VERIFY_PATTERN`.

---

### F4 — Windows como alvo primário de CI

**Problema.** O produto só sai em Windows e o código-base trata Windows como exceção: 7 testes de proteção de credencial pulados lá, 8 assertions que viram no-op lá, SSH testado só no caminho que não roda lá.

**Entrega.**
1. Job de CI `windows-latest` como **obrigatório**; POSIX vira job secundário.
2. Nenhum teste pode conter `process.platform` dentro do corpo — regra de lint que falha o build. Converta para `test.skipIf`, que reporta skip honestamente.
3. Para cada `skipIf` de Windows, escreva o equivalente Windows:
   - permissão de `connection.json` → ACL via `icacls`, **lendo a ACL de volta** para asserir;
   - symlink → junction;
   - `spawn-helper` → equivalente ou skip justificado e nomeado.
4. O runner imprime a **lista nomeada dos testes pulados com motivo**. Nenhum skip anônimo — a auditoria identificou 11 de 12 e o 12º segue desconhecido justamente por isso.
5. SSH parametrizado por `mux: [true, false]` nas duas plataformas; teste live contra container OpenSSH efêmero em vez de rig manual.

**Aceite:** CI verde no Windows; relatório com skips nomeados; nenhum `process.platform` em corpo de teste.

---

### F5 — Plano de capacidade unificado

**Problema.** Memória, skills e plugins existem **duas vezes**, com modelos de permissão diferentes e sem sincronização:

| Capacidade | Hermes nativo | OmniRoute MCP |
|---|---|---|
| Memória | `memory.memory_enabled` | `omniroute_memory_add/search/clear` |
| Skills | `skills/` + `HERMES_HOME/skills` | `omniroute_skills_*`, `github_skills_install` |
| Plugins | `plugins/` + loader | `plugin_install/activate/configure` |

**Entrega.** Uma camada de capacidade única (`agent/capability_plane.py`) que:
- registra **provedores** para cada capacidade (`memory`, `skills`, `plugins`), nativo e MCP;
- expõe uma API única ao agente e à UI;
- aplica **uma política só** — mesma aprovação, mesmo audit trail, mesmo taint (F1);
- resolve conflito de nome de forma determinística e **loga** quando duas fontes disputam a mesma chave;
- permite desativar um provedor inteiro por config.

Não remova nenhum dos dois lados. O objetivo é que exista **um lugar** onde a política é decidida, não dois.

**Aceite:** `omniroute_memory_add` e a memória nativa passam pela mesma verificação de permissão; um teste prova que desativar o provedor MCP de skills impede `github_skills_install`; conflito de nome entre skill nativa e skill MCP é reportado, não silencioso.

---

### F6 — Teto de gasto fora do alcance do agente

**Problema.** `omniroute_set_budget_guard` é uma **ferramenta**. Um limite que o agente pode desligar não é limite.

**Entrega.**
1. Teto por sessão e por dia em `config.yaml` sob `security.spend_ceiling`, aplicado no roteador — **fora da superfície de ferramentas**.
2. Remover `write:budget` do conjunto de escopos default (`DEFAULT_OMNIROUTE_MCP_SCOPES` já não o inclui — mantenha assim e adicione teste que impede reintrodução).
3. `post_api_request` acumula custo real; ao cruzar 80% o agente recebe aviso; ao cruzar 100% novas chamadas são **negadas** com `BLOCKED`, não com falha silenciosa.
4. Estimativa **antes** de executar: para uma tarefa com escopo definido, mostrar custo estimado e pedir confirmação acima de um limiar.
5. Só o usuário eleva o teto, pela UI, nunca o agente.

**Aceite:** teste em que o agente chama `omniroute_set_budget_guard` e o teto efetivo **não muda**; teste em que o custo acumulado ultrapassa o teto e a próxima chamada retorna `BLOCKED`.

---

### F7 — Modo local-only

**Problema.** Não existe forma de garantir que o conteúdo do workspace não saia para provedor remoto. Para quem mexe com código de cliente, isso é bloqueante.

**Entrega.** `security.local_only: true` que, **imposto no roteador e não no prompt**:
- restringe o roteamento a provedores locais (Ollama, LM Studio, qualquer endpoint em loopback);
- **nega** `omniroute_web_fetch`, `web_search`, `oneproxy_fetch`, Notion, Obsidian remoto e qualquer egresso;
- é visível na UI de forma permanente enquanto ativo;
- ao ser desligado, exige confirmação explícita e registra no audit trail.

O usuário tem `.ollama` e `.lmstudio` no home — detecte os modelos disponíveis e ofereça no seletor.

**Aceite:** com `local_only`, uma chamada a provedor remoto retorna `BLOCKED` com motivo; o indicador aparece na UI; desligar exige confirmação e gera entrada de auditoria.

---

### F8 — Lockfile de skills e MCP servers

**Problema.** `omniroute_github_skills_install` instala **instruções** que o agente depois segue. É um caminho de código não assinado para comportamento.

**Entrega.** `.hermes/capabilities.lock` (formato JSON, versionado no repo do usuário):
```json
{
  "version": 1,
  "skills":      [{"id":"product-studio","source":"bundled","sha256":"...","version":"0.2.0"}],
  "mcp_servers": [{"id":"omniroute","command_sha256":"...","package":"omniroute","version":"3.8.49"}],
  "plugins":     [{"id":"dz23-guardrail","sha256":"...","security_critical":true}]
}
```
- Na carga, verificar hash; divergência → **recusa carregar** e reporta o que mudou.
- `hermes capabilities update` recalcula, mostra o diff e pede confirmação.
- Instalação nova de skill exige aprovação e grava no lock.
- O `omniroute-mcp-policy.mjs` já faz verificação de nome e versão do pacote — estenda com o hash do `dist/**/server.js` e registre no lock.

**Aceite:** alterar um byte de uma skill instalada faz a carga falhar com mensagem clara; `capabilities update` mostra o diff antes de aceitar.

---

### F9 — Prova visual no relatório de tarefa

**Problema.** O relatório do guardrail lista arquivos alterados e ferramentas usadas, mas não prova que o resultado funciona.

**Entrega.** Estender `_write_task_report` com uma seção **Evidência**:
- comandos de verificação executados, com **exit code real** (o `_verification_exit_code` já captura isso);
- para produto com UI: screenshot do preview após o agente exercitar o fluxo, via Playwright, que já está no projeto;
- opcional: GIF curto do fluxo principal;
- custo real da sessão (depende de F6 entregar `cost_usd` no payload de `post_api_request` — hoje o campo não chega e o relatório sempre imprime `$0`);
- marcas de taint da sessão (F1): quais conteúdos externos entraram e quando.

Screenshots vão para `<HERMES_HOME>/task-reports/assets/<session>/`, com a mesma redação e as mesmas permissões do relatório.

**Aceite:** uma sessão que altera UI produz relatório com screenshot anexado e exit codes reais; sessão sem UI produz relatório sem seção de screenshot, sem erro.

---

## 4. U1 — WORKSPACE NO PADRÃO QODER/QUEST

**Enquadramento honesto:** isto **não é redesign**. Quase todo elemento da referência corresponde a algo que o Hermes já tem e não expõe. A entrega é uma casca de navegação que torna descobrível o que hoje só existe em slash command, arquivo de config ou skill em disco.

**Restrições invioláveis:**
- Reutilizar os primitivos existentes (`SectionHeading`, `Pill`, `EmptyState`, `Codicon`, tokens de tema). **Nenhuma biblioteca de UI nova.**
- **Nenhuma alteração em `main.ts`** nesta entrega, exceto novos canais IPC estritamente necessários — e cada canal novo valida seus argumentos.
- Todo texto novo entra em `en.ts`, `pt-br.ts` e `types.ts` no mesmo commit. Nada de string literal em componente.
- Preservar CSP, `contextIsolation`, `sandbox` e o modelo de preload nominal.

### 4.1 Sidebar esquerda (largura fixa, colapsável)

| Elemento | Mapeia para | Estado |
|---|---|---|
| **Nova tarefa** + atalho `Ctrl+N` visível | nova sessão | existe |
| **Fixados** | sessões marcadas | novo — persistir em estado local |
| **Tarefas** com ícones de visão, filtro e criar | sessões com Goal ativo | Goal existe; falta a lista |
| **Recentes** — workspace atual com caminho | workspace da sessão | existe |
| **Conversas** — com ponto de estado por item e badge **"Ação necessária"** | sessões; badge quando há aprovação pendente | `submit_pending` / `approval_required` já existem em `tools/approval.py:3623-3641` |
| **Agenda** | cron do Hermes + `omniroute-daily-health.py` | existe, sem UI |
| **Conhecimento** | Knowledge Cards de `.hermes/knowledge/` | definido em `references/knowledge-and-rules.md`, **sem implementação nem UI** |
| **Marketplace** | plugins e skills | `hermes:plugin:installDesktop` existe |
| Rodapé: avatar, nome, plano, **Atualizar**, medidor de uso, engrenagem | conta, atualização, custo (F6), configurações | atualização existe; medidor depende de F6 |

O badge **"Ação necessária"** é o item de maior valor da sidebar: hoje uma aprovação pendente numa sessão em segundo plano é invisível.

### 4.2 Paleta de contexto (`@`) — overlay central

Campo de busca único: *"Buscar contexto, plugins, agentes e mais"*. Linhas, na ordem da referência:

```
Arquivos        →  seletor com árvore do workspace              (fs-ipc já expõe readDir)
Pastas          →  idem, seleção de diretório
Anexo           →  arquivos e imagens locais                    (readFileDataUrlForAttach existe)
─────────────────────────────────────────────────────────────
Plugins         →  plugins carregados + estado                   (plugins.py já expõe a lista)
Agentes         →  roster do Product Studio                      (references/multi-agent-orchestration.md
                    "Agentes especializados para tarefas específicas")   define os 9 papéis)
Habilidades e comandos → skills + slash commands                 (ambos existem)
─────────────────────────────────────────────────────────────
[toggle] Spec   →  "Propor um plano primeiro e prosseguir após confirmação"
[toggle] Goal   →  "Definir um objetivo e trabalhar até concluir"
```

**O toggle Spec é o achado desta seção.** Ele corresponde exatamente ao gate que o Hermes já implementa: `/goal draft` produz o contrato e **pausa** com `paused_reason = "awaiting-spec-review"`, e `/goal resume` libera a construção. Hoje isso só existe como slash command e o usuário leigo nunca descobre. Ligar o toggle = chamar o caminho `draft`; a UI mostra o contrato renderizado com botões **Revisar** e **Construir**.

Ao corrigir isso, resolva também a divergência conhecida: o gateway pausa só para `draft` e o CLI pausa para qualquer contrato, e ambos usam `mgr.pause(...) or state`, que pode afirmar "pausado" quando a pausa falhou. Extraia uma função única para os três consumidores (gateway, CLI, UI).

**O toggle Goal** liga o modo objetivo com `goals.max_turns` visível e um progresso real — não uma barra decorativa.

### 4.3 Composer

```
Placeholder: "Planeje e construa, @ para contexto, / para comandos"
[+]  abre a paleta de contexto
[Agente ▾]   seletor de papel do roster
[Modelo ▾]   modelos reais de omniroute_list_models_catalog; "Auto" como padrão
[✨]         refinar prompt (opcional; só se houver implementação real por trás)
[🎤]         voz — Hermes já tem transcrição (hook pre_transcription existe)
[enviar]
```
Nenhum botão pode existir sem comportamento. Se `✨` não tiver implementação, **não coloque o botão**.

### 4.4 Estado vazio com sugestões acionáveis

Três a quatro sugestões que **executam de verdade** ao clicar, adaptadas ao workspace detectado:
```
▸ Desenvolver um fluxo de checkout de carrinho
▸ Elevar a cobertura de testes deste projeto para 80%
▸ Auditar a segurança deste repositório
▸ Pesquisar frameworks de agentes e produzir um relatório de seleção
```
Se não houver workspace aberto, ofereça primeiro o seletor "Trabalhar em: <projeto>".

### 4.5 Rail direita (ícones verticais)

Mapa do projeto · Terminal · Arquivos e diff · Relatório de tarefa · Preview.
Todos já existem no produto; a entrega é organizá-los num rail consistente.

### 4.6 Barra superior

`Editor ↗` (abrir no editor externo — `hermes:window:openInTerminal` e correlatos já existem), menu `…`, alternar painel, controles de janela.

### 4.7 Estados obrigatórios

Para **cada** superfície acima: `loading`, `vazio`, `erro`, `offline`, `permissão negada`, `sucesso parcial`. Todos em pt-BR. Um painel sem estado de erro é um painel que mente quando falha.

### 4.8 Acessibilidade

Ordem de foco previsível, navegação completa por teclado, `aria-label` em todo controle sem texto, contraste WCAG AA, `aria-live` nos indicadores que mudam de estado. Corrija de passagem o chip **"Acesso do agente ativo"** (`preview-browser-bar.tsx:188-196`), que hoje é texto fixo sem binding e some abaixo do breakpoint `lg`.

### 4.9 Aceite da U1

- Um usuário leigo, sem ler documentação, encontra e usa: Spec, Goal, Agentes, Habilidades, Agenda, Conhecimento e Marketplace.
- Nenhum botão sem comportamento; nenhuma string fora do i18n.
- pt-BR completo nas telas novas (a cobertura geral é tratada no prompt de correção).
- Aprovação pendente numa sessão em segundo plano aparece como **"Ação necessária"** na sidebar.
- Sem regressão em CSP, `contextIsolation`, `sandbox` ou preload.

---

## 5. ORDEM DE EXECUÇÃO

```
0.  Pré-requisito: Wave 0 do prompt de correção (commit da remediação P0)
1.  F1  taint tracking              independente · maior valor de segurança
2.  F3  fuzzer de guardrail         independente · barato · protege F1
3.  F4  Windows-first CI            independente · derruba metade dos P2 sozinho
4.  F6  teto de gasto               habilita o medidor de uso da U1
5.  F2  gravação e replay           habilita F9 e o gerador de testes
6.  F9  prova visual                depende de F2 e F6
7.  U1  workspace Qoder             depende de F6 (uso) e se beneficia de F1 (indicador)
8.  F7  modo local-only             independente
9.  F8  lockfile de capacidades     independente
10. F5  plano de capacidade         maior refactor · por último · exige F8 estável
```

F1, F3 e F4 são independentes entre si e podem sair em paralelo. **Comece por F1.**

---

## 6. GATE POR ENTREGA

Para cada F ou U concluída, na máquina Windows real, com saída anexada:
```
npm run typecheck · npm run lint · npm test
testes específicos da entrega
build · NSIS · secret scan
regressão completa
```
E o script de re-execução do guardrail da seção 4 de `audit/CODEX_R2_FIX_AND_REAUDIT.md` — baseline `18/18` destrutivos, `0/5` falsos positivos, gate fail-closed. **Qualquer número diferente é regressão.**

Descubra os scripts reais em `package.json` / `pyproject.toml`. Não invente comando se já houver script oficial.

Commit por entrega, mensagem descrevendo a capacidade. Sem push.

---

## 7. O QUE NÃO PODE SER QUEBRADO

`contextIsolation: true`, `sandbox: true`, `nodeIntegration: false` em todas as janelas · `setWindowOpenHandler` com `deny` incondicional · preload com API nominal, sem passthrough de canal · CSP e `hardenWebviewAttachment` · `execFile` com argv em array, sem `shell: true` · `resolveAllowedFsIpcPath` e `externalFileBlockReason` · `DEFAULT_OMNIROUTE_MCP_SCOPES` com 6 escopos e **sem `write:plugins`** · token local do OmniRoute em `safeStorage`, nunca ao renderer · **hardline floor** aplicado antes do `--yolo` · isolamento de canal do `_smart_approve` · `execute_code` em subprocesso com RPC autenticado · `request_tool_approval` fail-closed sem humano · o guardrail com `kind: backend` + `security_critical: true` e seus 18/18 · identidade lado-a-lado do Studio.

---

## 8. ENTREGA FINAL — BUILD, INSTALAÇÃO NO PC DO USUÁRIO E SMOKE

Nada disto é opcional. O usuário precisa **ver funcionando na máquina dele** antes da auditoria final.

### 8.1 Proteja os dados do usuário primeiro

Antes de instalar qualquer coisa por cima, faça backup do estado que a instalação atual carrega:
```powershell
$stamp = Get-Date -Format yyyyMMdd-HHmmss
$dest  = "$env:USERPROFILE\hermes-backup-$stamp"
New-Item -ItemType Directory -Path $dest | Out-Null

# estado do usuário — conversas, memória, config, relatórios, gravações, componentes gerenciados
Copy-Item "$env:USERPROFILE\.hermes"                    "$dest\hermes-home"        -Recurse -ErrorAction SilentlyContinue
Copy-Item "$env:APPDATA\Hermes OmniRoute Studio"        "$dest\userData"           -Recurse -ErrorAction SilentlyContinue
Copy-Item "$env:USERPROFILE\.omniroute"                 "$dest\omniroute"          -Recurse -ErrorAction SilentlyContinue

Get-ChildItem $dest | Format-Table Name, Length
```
Confirme que o backup existe e não está vazio **antes** de prosseguir. Se o backup falhar, **pare e avise o usuário**.

### 8.2 Build limpo e reproduzível

O instalador anterior foi gerado com `"dirty": true` — não era reconstruível por ninguém. Desta vez:

1. `git status` deve estar limpo para código (os artefatos de `audit/_raw/` já devem estar no `.gitignore`).
2. Rode o gate completo da seção 6 **antes** de empacotar. Build sobre suíte vermelha não sai.
3. Empacote com os scripts oficiais do projeto (descubra em `apps/desktop/package.json`; não invente comando).
4. Registre e anexe ao relatório:
   ```powershell
   Get-FileHash <caminho-do-instalador>.exe -Algorithm SHA256
   Get-Content apps\desktop\release\win-unpacked\resources\install-stamp.json
   ```
5. **`install-stamp.json` deve trazer `"dirty": false`** e o `commit` deve bater com `git rev-parse HEAD`. Se vier `true`, o build saiu de worktree sujo — **refaça**, não justifique.

### 8.3 Instalação

Instale na máquina do usuário, por cima da instalação existente (é o app dele, ele quer ver a atualização).

- **Feche o Hermes OmniRoute Studio antes.** Instalar com o app aberto é um dos cenários de falha que o instalador precisa tratar — teste isso separadamente, numa VM, não na instalação principal.
- **Não desinstale a instalação principal** como parte deste passo. Teste desinstalação em VM ou usuário Windows separado.
- Depois de instalar, registre:
  ```powershell
  Get-FileHash "$env:LOCALAPPDATA\Programs\HermesOmniRoute\HermesOmniRoute.exe" -Algorithm SHA256
  Get-Content "$env:LOCALAPPDATA\Programs\HermesOmniRoute\resources\install-stamp.json"
  ```
- **Paridade build × fonte:** compare tamanho e hash de cada componente gerenciado em `resources\` (`omniroute-mcp-bridge.mjs`, `omniroute-mcp-policy.mjs`, `omniroute-daily-health.py`, `dz23-guardrail\__init__.py`, `dz23-guardrail\plugin.yaml`, `product-studio-skill\`) contra a árvore commitada. **Divergência aqui significa que a build não é a fonte** — foi assim que a auditoria R2 descobriu que o instalador anterior continha código não commitado.

### 8.4 Smoke obrigatório no app instalado

Abra o aplicativo e exercite, anexando evidência (screenshot ou saída) de cada item:

```
startup limpo · onboarding · idioma pt-BR · navegação da sidebar nova
paleta @ (Arquivos, Pastas, Anexo, Plugins, Agentes, Habilidades)
toggle Spec  → produz contrato e PAUSA em awaiting-spec-review
toggle Goal  → progresso real, não barra decorativa
Agenda · Conhecimento · Marketplace
medidor de uso mostrando custo real (F6)
indicador de contexto externo aparecendo após um web fetch (F1)
badge "Ação necessária" quando há aprovação pendente em segundo plano
preview · terminal · arquivos/diff · relatório de tarefa com screenshot (F9)
modo local-only ligando e bloqueando egresso (F7)
restart preservando conversas e memória
shutdown limpo
```

E as provas que as auditorias anteriores nunca conseguiram fazer:
```
Guardrail ATIVO na UI, e `del /s /q` realmente bloqueado numa sessão real de agente
Taint: web fetch → npm install no turno seguinte → exige aprovação citando a fonte
Teto de gasto: agente chama omniroute_set_budget_guard e o teto efetivo NÃO muda
MCP ao vivo: tools/list resolvendo a divergência 106 × 107
Caveman: ligar/desligar e comprovar mudança de estado NO OmniRoute, não só no switch
       — depois RESTAURE o estado original
Escopo MCP: plugin_install retorna isError com missing_scopes no default
```

Inspecione, e anexe: console, network, logs do Electron, processos, uncaught exceptions, unhandled rejections. **Zero processos órfãos** após fechar (preview, node do bridge, PTY) — verifique com `Get-Process`.

### 8.5 Se algo quebrar na instalação

Não maquie. Registre como defeito confirmado, restaure o backup da seção 8.1 se necessário, e avise o usuário com: o que quebrou, em que passo, a saída real, e o caminho do backup.

---

## 9. AUDITORIA FINAL

**Só comece depois que a seção 8 estiver concluída e o aplicativo instalado estiver rodando na máquina do usuário.** A auditoria é sobre o produto instalado, não sobre o código no editor.

Execute a seção 5 de `audit/CODEX_R2_FIX_AND_REAUDIT.md` — auditoria independente, você como terceiro em quem não confia — e produza `audit/HERMES_OMNIROUTE_AUDIT_R4.md` cobrindo, além do quadro já definido lá:

```text
TAINT_TRACKING_ATIVO=<sim|não>   TAINT_TESTES=<X/7>
REPLAY_FUNCIONAL=<sim|não>       FIXTURES_GERADAS=<N>
FUZZER_VARIANTES=<N>             FUZZER_ESCAPES=<0|N>
CI_WINDOWS_OBRIGATORIO=<sim|não> SKIPS_NOMEADOS=<sim|não>
TETO_DE_GASTO_INVIOLAVEL=<sim|não>
LOCAL_ONLY_IMPOSTO_NO_ROTEADOR=<sim|não>
LOCKFILE_VERIFICA_HASH=<sim|não>
RELATORIO_COM_EVIDENCIA_VISUAL=<sim|não>
UI_SEM_BOTAO_MORTO=<sim|não>     PT_BR_TELAS_NOVAS=<%>

BUILD_LIMPO=<sim|não>            INSTALL_STAMP_DIRTY=<true|false>
INSTALADOR_SHA256=
EXECUTAVEL_INSTALADO_SHA256=
PARIDADE_BUILD_x_FONTE=<sim|não — divergências, se houver>
APP_INSTALADO_EXERCITADO=<sim|não>
PROCESSOS_ORFAOS=<0|N>
UNHANDLED_REJECTIONS=<0|N>
GUARDRAIL_ATIVO_NA_UI=<sim|não>  DEL_S_Q_BLOQUEADO_EM_SESSAO_REAL=<sim|não>
MCP_TOOLS_LIVE=<N>               CAVEMAN_ESTADO_COMPROVADO=<sim|não>
BACKUP_DO_USUARIO=<caminho>
```

Se alguma capacidade não puder ser comprovada, registre `BLOCKED_BY_EXTERNAL_DEPENDENCY` com `dependency`, `affected_feature`, `what_was_verified`, `what_could_not_be_verified`, `exact_requirement_to_unblock`. **Não use mock para converter esse estado em PASS.**

Se discordar de qualquer decisão de design deste documento, registre `DISPUTED_DESIGN` com motivo e alternativa antes de implementar. Não construa algo que você acredita estar errado só porque o documento mandou.

---

## 10. LEMBRETE

Este produto passou em ~1.549 testes enquanto o plugin de segurança não carregava e três gates eram contornáveis por `del /s /q`, por `../` e por `echo`. A rodada de correção resolveu isso de verdade.

O que essas nove capacidades adicionam não é superfície — o Hermes já tem mais superfície que qualquer concorrente. É **evidência**: taint que prova de onde veio a instrução, replay que prova que o comportamento não mudou, exit code que prova que o teste rodou, screenshot que prova que a tela funciona, e teto de gasto que o próprio agente não desliga.

Superfície é o que todo mundo tem. Evidência é o que ninguém entrega.
