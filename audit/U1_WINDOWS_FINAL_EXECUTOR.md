# U1 — Executor Final no Windows (validação real)

Prompt ÚNICO para o executor local (Claude Code/Codex) no PC Windows, dentro de
`C:\Users\you\Documents\Codex\Hermes-OmniRoute`. Fecha o que este ambiente
remoto não pôde VALIDAR (não implementar): IPC real ao gateway, runtime OpenWA,
QR, build/NSIS, app instalado e inspeção visual.

Contexto: as camadas de domínio do U1 já estão IMPLEMENTADAS e testadas no repo
(component + contract PASS, com canaries). Este executor faz a validação real e a
ligação de UI/IPC que exige o app rodando. NÃO reescrever as camadas de domínio;
consumi-las.

Regras duras: NÃO PUSH. NÃO RELEASE. NÃO bundlar OpenWA/CodeQL. NÃO quebrar
RAPTOR/OpenWA/LOCAL_ONLY. NÃO declarar E2E/CONNECTED com mock. QR real =
WAITING_FOR_HUMAN_QR_SCAN (só para auth/send/receive), não bloqueia o resto.

## 0. Gates base (rodar primeiro; parar se vermelho)

```powershell
cd C:\Users\you\Documents\Codex\Hermes-OmniRoute
npm install                     # raiz (workspaces)
python -m pytest tests/security_research tests/whatsapp_provider tests/agent/test_local_only.py -q  # esperado: 227 passed
pnpm -C apps/desktop typecheck
pnpm -C apps/desktop test:ui    # inclui as suítes de domínio U1 novas
pnpm -C apps/desktop lint
```

## 1. Ligação de UI + IPC (consumir as camadas de domínio já prontas)

Para cada módulo, criar o transporte real (IPC ao gateway Python) que implementa
a interface já definida, e a view React que consome o view-model já testado.
NÃO reimplementar a lógica — ela está pronta e coberta por teste.

| módulo U1 | domínio pronto (consumir) | o que o executor liga |
|---|---|---|
| Security Research | `app/security-research/{types,transport,validation,model}.ts` | transporte IPC→RAPTOR (`security_research/adapter.py`), view + pane; findings/report → sistema de artifacts existente |
| Model Routing | `app/model-routing/routing.ts` | ler o estado real de rota do runtime OmniRoute; mostrar o rótulo no model-pill |
| Context panel | `app/context-panel/context-model.ts` | registrar pane com abas (o tree já empilha), ligar aos stores reais; validar docking/resize/persistência |
| Goals | `app/goals/goal-authoring.ts` | ligar "transformar em Goal" ao composer/agente; transporte de create/cancel/resume |
| Agents | `app/agents/agent-authoring.ts` | transporte create/edit/delegate/cancel→runtime de subagentes |
| Memory | `app/memory/memory-inline.ts` | ligar affordance ao provider de memória; Forget quando suportado |
| WhatsApp | `app/whatsapp/whatsapp-surface.ts` | transporte de status→`whatsapp_provider`; QR via IPC allowlisted |

Verificação de cada: `pnpm -C apps/desktop test:ui` continua verde; component
tests da view novos; nenhum `any`/mock em produção; tsc limpo.

## 2. RAPTOR real IPC

```powershell
# no Linux/WSL2 (sandbox do RAPTOR é Linux) — configurar o checkout do RAPTOR
# rodar via adapter: describe (preflight) → scan (semgrep) contra um projeto de teste
```
Validar: preflight retorna health real; scan gera findings reais; findings/report
viram artifacts; modo exec-untrusted → BLOCKED_BY_PLATFORM_SECURITY (não roda no
Windows nativo). `RAPTOR_REAL_IPC` só vira PASS aqui.

## 3. OpenWA runtime + QR (gate humano)

```powershell
$env:WA_API_KEY = "<chave-forte-min-16>"
npx --yes @open-wa/wa-automate@4.76.0 --session hermes-test --port 8080 --host 127.0.0.1 --no-api-key-in-argv
# escanear o QR com o telefone  ← WAITING_FOR_HUMAN_QR_SCAN
```
UI deve refletir QR_REQUIRED→CONNECTED reais; enviar para número CONTROLADO;
sem número controlado → `BLOCKED_BY_REQUIRED_TEST_RECIPIENT`. Nunca declarar
CONNECTED sem estado real.

## 4. Build / package / NSIS / app instalado

```powershell
pnpm -C apps/desktop build
pnpm -C apps/desktop test:desktop:nsis      # ou o gate NSIS do projeto
# instalar e abrir:  C:\Users\you\AppData\Local\Programs\HermesOmniRoute
```
NÃO incluir OpenWA/RAPTOR/CodeQL no instalador.

## 5. Inspeção visual (abrir o app) + DevTools

Abrir o Hermes e inspecionar: Workspace U1, sidebar (Agents/Memory novos no nav),
chat, composer, Context panel (abas escondem quando vazias), Agents, Goals,
Memory, Security Research, WhatsApp, command palette, light/dark, janelas
wide/normal/narrow. DevTools: console, network, React warnings, Electron logs,
uncaught/unhandled. Corrigir o que aparecer.

## 6. E2E U1

```
launch → U1 → open project → new task → send → model/agent → tool → response →
artifact → Context panel → Files → Changes → Preview → Transform into Goal →
Security Research (describe/scan) → continue → restart → resume
```
Sem mock para declarar PASS.

## 7. Regressão final

`RAPTOR, OpenWA, MCP, Agents, Memory, Goals, Product Studio (skill), Preview,
SSH, Caveman, Guardrails, Cron` — revalidar. Rodar a suíte completa do desktop
(ui + electron) e a suíte Python.

## 8. Matriz a preencher pelo executor (validação real)

Para cada módulo, virar `PASS` os campos hoje `BLOCKED`:
`*_REAL_IPC`, `*_VISUAL_VALIDATION`, `U1_INSTALLED_APP`, `U1_E2E`,
`U1_ACCESSIBILITY`. Só então `OPEN_INTERNAL_FIXABLE=0` pode ser determinado.
