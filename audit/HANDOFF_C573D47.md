# HANDOFF REANCORADO — HERMES OMNIROUTE STUDIO
## Substitui o handoff ancorado em `e0f1458` (obsoleto em 5 commits)

Gerado por auditoria independente em 2026-08-22, a partir de inspeção real do disco e do Git.

---

## 1. IDENTIDADE VERIFICADA

```text
checkout   C:\Users\zodyp\Documents\Codex\Hermes-OmniRoute
toplevel   idêntico ao checkout                              ✔
branch     feature/hermes-omniroute-studio                   ✔
HEAD       c573d4791a77928f8772e8e3d3d3cbb24799d3bf          ← ÂNCORA NOVA
remote     origin → https://github.com/NousResearch/hermes-agent.git
backup     C:\Users\zodyp\Documents\Codex\hermes-r2-backup-20260821-185318
```

**Se o HEAD divergir de `c573d47`, pare e diagnostique antes de editar.**

### Linhagem desde o handoff anterior

```text
c573d479  feat(replay): compare model decisions without executing tools     ← HEAD
c14c637f  feat(audit): add redacted session replay and visual evidence
9d61f33f  feat(security): enforce user-owned spend ceilings
0c2a5a4b  test(ci): make Windows the primary platform contract
6a5b3acd  fix(test): satisfy lint for taint status contract
e0f14584  test(security): fuzz destructive command guardrails    ← âncora antiga
900234c   feat(skills): bundle creative toolkit and superpowers
9ae3e9d   feat(security): track external context provenance
114e357   feat(studio): close R2 product and platform gaps
e1c0a1f   fix(security): close R2 package and desktop boundaries
0cc4af1   feat(studio): secure OmniRoute desktop integration baseline
```

**Correção ao handoff anterior:** a seção "trabalho em andamento não commitado — F4" está **obsoleta**. F4 foi entregue no commit `0c2a5a4b` (lmprado.dz23, 21/08 23:07) com 14 arquivos, `+308/-68`, incluindo `windows-primary.yml` novo (+123) e `check-platform-test-guards.mjs` (+64). Não tente "fechar F4".

---

## 2. ESTADO DAS ENTREGAS

| Wave | Status | Commit | O que auditar |
|---|---|---|---|
| F1 taint tracking | commitado | `9ae3e9d` + `6a5b3acd` | reexecutar os 41 testes; provar escalonamento real numa sessão |
| Skills criativas | commitado | `900234c` | **inventário divergente — ver §4 R3** |
| F3 fuzzer | commitado | `e0f1458` | reexecutar; baseline `665 passed` |
| F4 CI Windows-first | commitado | `0c2a5a4b` | **nunca auditado pós-commit** |
| F6 teto de gasto | commitado | `9d61f33f` | provar que o agente não altera o teto |
| F2 replay | commitado | `c14c637f` + `c573d479` | provar replay + geração de teste |
| F9 prova visual | commitado | `c14c637f` | provar screenshot + exit code real no relatório |
| **U1 workspace** | **pendente** | — | ver `HERMES_DESIGN_SYSTEM.md` |
| **F7 local-only** | **pendente** | — | `audit/CODEX_HERMES_EVOLUTION.md` |
| **F8 lockfile** | **pendente** | — | idem |
| **F5 capability plane** | **pendente** | — | idem, por último |

---

## 3. WORKTREE — ESTADO REAL

```text
CONFIRMADO SUJO (rc=0)
  M  apps/desktop/electron/entitlements.mac.inherit.plist
  M  apps/desktop/electron/entitlements.mac.plist
  M  apps/desktop/electron/preview-reach.e2e.mts
  M  apps/desktop/scripts/.gitignore          ← APENAS CRLF, não commitar
  M  tools/neutts_samples/jo.txt              ← APENAS CRLF, não commitar
  ?? audit/CODEX_HERMES_EVOLUTION.md          (único untracked de código)

CONFIRMADO LIMPO
  .github · integrations · agent · gateway · apps/desktop/e2e
  apps/desktop/src/{app,i18n,types} · apps/desktop/vitest.config.ts
  staged = 0 · stash = 0

INCONCLUSIVO — timeout no mount, NÃO tratar como limpo
  apps/desktop/src/{components,lib,store} · plugins · hermes_cli
  git diff --check  (rc=124, saída vazia por timeout)
```

**Primeira tarefa obrigatória:** rodar `git status --short --branch` completo na máquina Windows (é rápido lá) e publicar a lista real. A auditoria remota não conseguiu fechar essa lista por limitação do bridge de arquivos.

---

## 4. ACHADOS DESTA AUDITORIA

### R1 · P2 · Poluição CRLF no worktree
`apps/desktop/scripts/.gitignore` e `tools/neutts_samples/jo.txt` diferem do HEAD em **exatamente 1 byte cada** (17 vs 16 e 263 vs 262), ambos `with CRLF line terminators`. `core.autocrlf` está **não definido** apesar de existir `.gitattributes` (1254 bytes).

Não são alterações intencionais. Vão poluir todo commit futuro.

**Correção:** decidir a política (`core.autocrlf=input` ou `.gitattributes` com `* text=auto eol=lf`), aplicar, e restaurar os dois arquivos. **É a única exceção em que um checkout pontual é justificado** — e mesmo assim, faça backup do byte-a-byte antes e registre no relatório.

### R2 · P2 · `vitest.config.ts` — autoria resolvida
O handoff anterior pedia investigar um `testTimeout: 30_000` "sem autoria confirmada". **Resolvido:**

```text
e30388e4  (upstream)                                        testTimeout: 15_000 (com comentário justificando)
22d1e77f  test(desktop): stabilize cross-platform gates      15_000 → 30_000
62ca9bda  test(desktop): isolate async view regressions      30_000 → 60_000
0c2a5a4b  (F4)                                               +7 linhas no arquivo
```

O arquivo está **commitado e limpo**. Não há alteração órfã. Item encerrado.

**Mas fica uma pergunta legítima para o R4:** o timeout subiu 15s → 30s → 60s em três commits. Timeout crescente costuma ser sintoma de teste lento ou flaky sendo acomodado em vez de corrigido. Investigue quais testes precisam de 60s e se algum está mascarando travamento real.

### R3 · P2 · Inventário de skills maior que o declarado
O handoff lista: `gsap`, `img2threejs`, `motion-design`, `design-toolkit`, `superpowers`.

No disco, `skills/creative/` contém **também**: `humanizer`, `architecture-diagram`, `ascii-art`, `ascii-video`, `baoyu-infographic`, `claude-design`, `comfyui`, `design-md`.

**Mais skills foram empacotadas do que qualquer documento declara.** O R4 precisa reconciliar: inventário real no disco × inventário no instalador × inventário documentado × licenças por origem.

### R4 · Licenciamento — VERIFICADO E CORRETO (crédito, não achado)
```text
skills/creative/gsap/LICENSE
skills/creative/img2threejs/LICENSE
skills/creative/motion-design/LICENSE
skills/creative/humanizer/LICENSE
skills/creative/design-toolkit/LICENSE.daymade
skills/creative/design-toolkit/LICENSE.impeccable
skills/creative/design-toolkit/LICENSE.nextlevelbuilder
skills/creative/design-toolkit/frontend-design/LICENSE.txt
+ SOURCES.json em skills/creative e em design-toolkit
```
GSAP declara `license: MIT` nos manifests e documenta que, após a aquisição pela Webflow, todos os plugins são livres inclusive para uso comercial, sem chave nem membership. **Para o release open source, esta parte está resolvida.**

### R5 · P3 · Timeout crescente do vitest — ver R2.

---

## 5. O QUE FALTA — ORDEM

```
0.  Reancorar: git status completo no Windows · limpar CRLF · política de line-ending
1.  Auditar o que já foi commitado e nunca verificado pós-commit:
       0c2a5a4b (F4) · 9d61f33f (F6) · c14c637f + c573d479 (F2/F9)
       reexecutar: guardrail 18/18 e 0/5 · fuzzer 665 · testes F1
2.  U1  workspace              → HERMES_DESIGN_SYSTEM.md
3.  F7  local-only             → audit/CODEX_HERMES_EVOLUTION.md
4.  F8  lockfile               → idem
5.  F5  capability plane       → idem, por último
6.  Multiplataforma e mobile   → HERMES_MULTIPLATFORM.md
7.  Prontidão open source      → HERMES_OPENSOURCE_READINESS.md
8.  Gate final · build limpo · instalação · smoke · auditoria R4
```

---

## 6. REGRAS QUE NÃO MUDAM

`DO_NOT_PUSH_YET` · commit isolado por entrega · sem PR nem release sem pedido explícito.
Proibido `git reset --hard`, `git clean -fd`, `git checkout .`, `git restore .`, `git stash drop` sobre trabalho existente.
Use `npm`. Não introduza pnpm nem bun.
Não altere outro checkout, servidor ou terminal interativo. Comandos não interativos, com `workdir` explícito.
Nunca declare sucesso sem exit code real anexado.

**Hardlines que não podem regredir:** `contextIsolation: true`, `sandbox: true`, `nodeIntegration: false` · `setWindowOpenHandler` negando abertura arbitrária · preload nominal sem passthrough de canal · CSP e `hardenWebviewAttachment` · `execFile` com argv, sem `shell: true` para dado externo · `resolveAllowedFsIpcPath` e `externalFileBlockReason` · `DEFAULT_OMNIROUTE_MCP_SCOPES` com 6 escopos e sem `write:plugins` · token OmniRoute em `safeStorage`, nunca no renderer nem em log · hardline floor antes de qualquer modo yolo · aprovação fail-closed sem humano · guardrail `kind: backend` + `security_critical: true` · nenhuma credencial em commit, relatório, screenshot ou log.

---

## 7. NOTA SOBRE O AUTOR DESTE DOCUMENTO

Esta auditoria roda de um container Linux com ponte de arquivos para a máquina Windows. **Não executa o toolchain Windows** — `npm`, Electron, electron-builder, NSIS e o servidor MCP vivo são inalcançáveis daqui. Foi verificado que mesmo com computer use os terminais só permitem *click*, não digitação, então não há contorno.

Portanto: tudo neste documento marcado como FATO vem de leitura de disco e Git, ou de execução de código Python isolado. **Nada aqui é resultado de suíte de teste executada.** Quem executa é você, na máquina real, e a evidência é o exit code.
