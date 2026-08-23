# ESTADO DE EXECUÇÃO AUTÔNOMA — Hermes OmniRoute Studio

> **Como retomar:** leia este arquivo, depois `git status`, depois `git log -5`.
> Continue da primeira linha `EM EXECUÇÃO` ou, se não houver, da primeira `PENDENTE`
> da fila. **Nunca reinicie a missão do zero.**

**Última atualização:** 2026-08-22 · rodada R4-01
**Repositório:** `C:\Users\zodyp\Documents\Codex\Hermes-OmniRoute`
**Branch:** `feature/hermes-omniroute-studio`

---

## 1. MISSÃO

Levar o Hermes OmniRoute Studio de "worktree com trabalho não commitado" a
**release pública auditada**, passando por: auditar → implementar → testar →
inspecionar → corrigir → retestar → buildar → validar → publicar → auditoria
final com 3 agentes independentes → corrigir → retestar → validar.

---

## 2. ESTADO NO INÍCIO DESTA RODADA

```
HEAD          0bb230c  fix(security): close release audit regressions
commits       20
versão        0.17.0-omniroute.1
worktree      14 arquivos modificados + apps/mobile inteiro não rastreado
remote        origin -> NousResearch/hermes-agent  (ERRADO: é o upstream)
identidade    lmprado.dz23 <lmprado.dz23@gmail.com> (dos commits existentes;
              o gitconfig do Windows não é visível da VM Linux)
instalado     do commit 9d80176, dirty:true, 20 commits atrás
```

---

## 3. FILA DE EXECUÇÃO

Legenda: `PENDENTE` · `EM EXECUÇÃO` · `FEITO` · `BLOCKED_BY_EXTERNAL_DEPENDENCY`

### Bloqueadores de publicação

| # | Tarefa | Estado |
|---|---|---|
| B1 | Commit integral da árvore válida | EM EXECUÇÃO |
| B2 | Remote do fork + proteção do upstream contra push | BLOCKED_BY_EXTERNAL_DEPENDENCY |
| B3 | Secret scan do histórico completo (`--all`) | FEITO — gitleaks 8.28.0 sobre 22 commits/251MB: 0 achados, exit 0; `.gitleaks.toml` + workflow; canários provam que um PAT real ainda é detectado |
| B4 | Remover `<<PREENCHER>>` — contatos de segurança/governança | BLOCKED_BY_EXTERNAL_DEPENDENCY |
| B5 | Build reproduzível: release falha com worktree sujo + SHA-256 | FEITO — `write-release-checksums.mjs` (SHA256SUMS.txt + BUILD-PROVENANCE.json), recusa árvore suja/commit placeholder/release vazio, 13 testes |
| B6 | Inventário de licenças + `SOURCES.json` + teste que falha sem origem/licença | FEITO — `skills/PROVENANCE.json` + `tests/skills/test_skill_provenance.py` (7 testes) + `audit/SKILL_LICENSE_INVENTORY.md` |

### Testes e gates

| # | Tarefa | Estado |
|---|---|---|
| T1 | Suíte Electron/desktop no container (typecheck, lint, vitest) | PARCIAL — `tsc --noEmit` limpo; vitest `ui` 5379/5379; vitest `electron` 1598 passed/9 skipped. Falta: lint |
| T2 | Suíte Python completa relevante (approval, goals, plugins, gateway) | PARCIAL — `tests/skills` 1797/1797, `tests/hermes_cli` por arquivo: 3 falhas em 240 arquivos (1 era o vazamento R5-02, já corrigido; 2 são do ambiente do contêiner). Falta: varredura completa de `tests/` com HOME limpo |
| T3 | Suíte web (build, typecheck, lint, vitest) | FEITO — 359 passed, exit 0 |
| T4 | Dependency audit / supply-chain | PENDENTE |
| T5 | Clean-install test | PENDENTE |

### Produto

| # | Tarefa | Estado |
|---|---|---|
| P1 | Interface U1 (sidebar, tarefas em background, paleta @, composer) | PARCIAL — ver §U1 |
| P2 | Passe responsivo mobile (M1.3) | PENDENTE |
| P3 | APK ↔ gateway: tela de conexão, HTTP nativo, token no Keystore | PENDENTE |
| P4 | pt-BR no `web/src/i18n` | FEITO — 713 chaves, 0 faltando, 0 lusitanismos, 6 testes verdes |
| P5 | Product/Design Studio (§4 do design system) | PENDENTE |
| P6 | CI pública segura (roda em PR de terceiro sem segredos) | PENDENTE |
| P7 | Builds macOS/Linux (AppImage/deb) com prova | PENDENTE |

### Release e auditoria final

| # | Tarefa | Estado |
|---|---|---|
| R1 | Release candidata: versão, changelog, artefatos, hashes | PENDENTE |
| R2 | Publicação | BLOCKED_BY_EXTERNAL_DEPENDENCY (depende de B2) |
| R3 | Auditoria com 3 agentes independentes (A/B/C) | PENDENTE |
| R4 | `audit/FINAL_THREE_AGENT_REVIEW.md` consolidado | PENDENTE |
| R5 | Correção dos achados + reteste | PENDENTE |
| R6 | Segunda revisão pelos 3 agentes | PENDENTE |
| R7 | Validação da release final | PENDENTE |

---

## 4. BLOQUEIOS EXTERNOS REGISTRADOS

### B2 — remote do fork
```
BLOCKED_BY_EXTERNAL_DEPENDENCY
dependency  = repositório GitHub na conta do usuário + credencial de push
evidência   = `git remote -v` devolve NousResearch/hermes-agent para fetch E push;
              `gh` não existe nem na VM do usuário nem no container.
o que fiz   = comandos exatos prontos em audit/OPENSOURCE_PRE_PUBLICACAO.md §P0-1
o que segue = todas as demais tarefas continuam; só a publicação depende disto
```

### B4 — canais de contato
```
BLOCKED_BY_EXTERNAL_DEPENDENCY
dependency  = endereço de e-mail/canal que o usuário controla
motivo      = um canal de denúncia inventado é pior que nenhum: o pesquisador
              acredita que reportou e espera 90 dias
arquivos    = SECURITY.md, CODE_OF_CONDUCT.md, .github/ISSUE_TEMPLATE/config.yml
```

### Toolchains ausentes no ambiente de execução
```
BLOCKED_BY_EXTERNAL_DEPENDENCY
- Android SDK/Gradle  -> não é possível gerar .apk aqui (projeto Gradle gerado e endurecido)
- Windows/NSIS        -> não é possível gerar o instalador aqui (script pronto no repo)
- macOS/notarização   -> exige conta Apple Developer
```

---

## 5. HISTÓRICO DE RODADAS

### R3 (rodada anterior) — FEITO
- Guardrail: 3 furos novos fechados (executores remotos de pacote, evasão do
  `--target`, fork bomb genérica). `304 passed / 4 failed` vs baseline
  `233 passed / 4 failed` — mesmo conjunto de falhas, zero regressão.
- CRLF: 691 arquivos + `* text=auto eol=lf`. Achado funcional: `./hermes` e os
  serviços s6 quebrariam o boot do container.
- pt-BR desktop: medido 98.5%; teste de percentual virou allowlist nominal.
- PWA: manifest, ícones, service worker à mão, 44 testes de política de cache.
- `gateway-origin`: 40 testes.
- Android: projeto Capacitor gerado e endurecido.
- HERMES-025: `start_goal()` — portão de revisão de plano numa função só, 11 testes.
- Governança: CODE_OF_CONDUCT, CHANGELOG, roteamento de segurança do fork.

---

## 6. REGRAS OPERACIONAIS APRENDIDAS (não redescobrir)

1. **Saída vazia sem exit code verificado é INCONCLUSIVO, nunca "limpo".**
   O mount do worktree é lento; `git status`/`git diff` de árvore inteira estoura
   timeout e devolve stdout vazio com `rc=124`.
   Errado: `cmd | head -30; echo $?` — o `$?` é do `head`, sempre 0.
   Certo: `cmd > /tmp/out 2>/dev/null; rc=$?; echo $rc; cat /tmp/out`
2. **Processos em background não sobrevivem entre chamadas de `device_bash`.**
   Não dá para paralelizar assim; divida o pathspec em lotes de ~40s.
3. **`device_bash` não apaga arquivos.** Mova para `_to_delete/`.
4. **Verificar correção de segurança injetando a regressão de volta**, para provar
   que o teste morde. Teste verde sem isso não prova nada.

---

## §U1 — o que a auditoria da UI encontrou (2026-08-22)

A tarefa P1 estava registrada como se a interface não existisse. Auditando o
código real de `apps/desktop/src` (588 arquivos `.tsx`), quase tudo já existe —
e reimplementar seria exatamente o que o próprio briefing proíbe:

| item de "U1" | situação real |
|---|---|
| sidebar | **existe** — `app/chat/sidebar/` (1902 linhas): busca FTS, sessões fixadas/recentes, projetos, worktrees, cron, filtros por status/projeto/perfil, lista virtualizada, ⌘B |
| composer | **existe** — `app/chat/composer/` com editor rich contenteditable, anexos, drop, paste de imagem, fila de follow-up (⌘⏎), voz, pop-out, undo próprio, 42 arquivos de teste |
| paleta `@` | **existe** — `hooks/use-at-completions.ts`: `@file:` `@folder:` `@url:` `@image:` `@tool:` `@git:`, `@diff`, `@staged`, com navegação de pastas e chips |
| paleta de comandos | **existe** — `app/command-palette/` (~1400 linhas): sessões, projetos, temas com preview, catálogo de settings, contribuições de plugin |
| shell/layout | **existe** — árvore de panes redimensionáveis (`components/pane-shell/tree/`), presets, painéis flutuantes, overlays em viewport estreita |
| **tarefas em background** | **era a lacuna real** |

A informação de trabalho em segundo plano existia em **quatro** superfícies, e
nenhuma respondia "o que está rodando agora?": a status stack do composer só
mostra a sessão aberta; o overlay Agents cobre a tela e só mostra subagentes; a
statusbar dá um número sem o quê; os dots da sidebar dão uma cor sem o porquê.
Com cinco sessões trabalhando, era preciso abrir as cinco.

**Entregue: `app/mission-control/`** — um pane de verdade na árvore (à direita,
escondido até ser pedido pelo ⌘K "Toggle Mission Control"), que agrega goals,
subagentes e processos de fundo de **todas** as sessões, ordenados por urgência
(falha antes de execução: falha não muda sozinha), com parar/dispensar
endereçados pelo id de RUNTIME e abrir-sessão pelo id ARMAZENADO.

Consome os mesmos stores e as mesmas ações da status stack — nenhuma segunda
implementação. Lógica de agrupamento e ordenação isolada em `rows.ts`, testável
sem React.

Cobertura: 11 testes da projeção + 9 do painel montado contra os stores reais,
incluindo o teste que impede o erro caro (usar o id armazenado para matar
processo mataria o processo de outra sessão, em silêncio). i18n em en, pt-BR e
zh; `tsc --noEmit` limpo.

Resta de P1, agora com escopo honesto: unificar Agents e Command Center como
panes da árvore (hoje são overlays modais que não coabitam com o chat) e cobrir
`command-palette/index.tsx` com teste (1400 linhas sem nenhum).
