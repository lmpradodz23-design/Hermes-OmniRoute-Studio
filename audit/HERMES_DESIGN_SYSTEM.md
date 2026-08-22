# HERMES OMNIROUTE — DESIGN SYSTEM E WORKSPACE (U1)

Especificação de design e implementação. Ancorada em reconhecimento real do repositório em `c573d47`.

---

## 1. PRIMEIRO: O QUE JÁ EXISTE

O design system **já existe e é maduro**. Praticamente nada aqui é para ser criado do zero — é para ser **composto**. Reimplementar qualquer item desta lista é regressão, não progresso.

### 1.1 Primitivos — `apps/desktop/src/components/ui/` (349 arquivos em `components/`)

```text
button · input · field · checkbox · badge · alert · loader · kbd · avatar-chip
dialog · confirm-dialog · context-menu · dropdown-menu · actions-menu · command
empty-state · error-state · action-status · glyph-spinner · disclosure-caret
codicon · favicon · file-type-icon · connector-card · connector-logo
copy-button · generate-button · diff-count · drop-affordance · color-swatches
fade-scroll · fade-text · decode-text · highlight-matches · keyboard-first
```

Existe `command.tsx` — **a paleta de comando já tem primitivo.** A paleta `@` da U1 é composição, não construção.

### 1.2 Temas — `apps/desktop/src/themes/`

```text
presets.ts          skins: nous, catppuccin, everforest, solarized (light/dark)
install.ts          buildThemeFromMarketplace — importa tema do VS Code Marketplace
color.ts            manipulação de cor
context.tsx         provider de tema
accent-override.ts  troca de cor de destaque
backend-sync.ts     sincroniza tema com o backend
profile-theme.ts    tema por perfil
```

Os skins são **derivados de extensões reais do VS Code** pelo mesmo caminho de um import de Marketplace. A regra do arquivo é explícita e deve ser respeitada: *"Re-convert from the upstream extension rather than hand-editing hexes; hand edits drift from upstream silently and can't be re-derived."*

### 1.3 Base CSS — `apps/desktop/src/styles.css`
Tailwind 4 · `@custom-variant dark` · codicons · KaTeX · **override global de `prefers-reduced-motion`** · pausa de animação quando a janela não está visível.

### 1.4 Camada compartilhada — `apps/shared/` (`@hermes/shared`)
```text
skin.ts · translucency.ts · websocket-url.ts · json-rpc-gateway.ts
backend-scope.ts · cron-trigger-controller.ts · skill-scaffold.ts · billing-*.ts
```

> **DECISÃO ASSUMIDA: os tokens de design canônicos passam a morar em `apps/shared/src/skin.ts`.**
> Justificativa: `skin.ts` já é compartilhado entre desktop e web, e é o único lugar onde um token pode servir Electron, navegador e o futuro APK sem duplicação. Desktop e `web/` consomem dali; nenhum cliente define paleta própria.

---

## 2. AS DUAS REFERÊNCIAS SÃO A MESMA ARQUITETURA

Claude Desktop e Qoder/Quest convergem no mesmo esqueleto. Não há conflito a resolver:

```text
┌────────────┬───────────────────────────────┬──────────────┐
│  SIDEBAR   │           CENTRO              │  RAIL DIREITA│
│            │                               │              │
│ ação       │  estado vazio com sugestões   │  preview     │
│ primária   │  ─ ou ─                       │  terminal    │
│            │  conversa / tarefa            │  arquivos    │
│ navegação  │                               │  diff        │
│ sessões    │  ┌─────────────────────────┐  │  relatório   │
│ com estado │  │ COMPOSER                │  │              │
│            │  │ @ contexto · / comandos │  │              │
│ rodapé:    │  │ agente ▾ · modelo ▾     │  │              │
│ conta/uso  │  └─────────────────────────┘  │              │
└────────────┴───────────────────────────────┴──────────────┘
```

Diferença real entre as duas: o Claude Desktop tem um alternador **Início / Code** no topo da sidebar e um painel de **tarefas em segundo plano**; o Qoder tem a **paleta `@` central** com toggles de Spec e Goal. **Adote os dois** — são complementares, e o Hermes tem substrato para ambos.

---

## 3. U1 — ESPECIFICAÇÃO DO WORKSPACE

**Restrições invioláveis:**
- Compor os primitivos de §1.1. Nenhuma biblioteca de UI nova. Nenhum primitivo duplicado.
- Tokens de `@hermes/shared/skin.ts`. Nenhuma cor literal em componente.
- Toda string em `en.ts`, `pt-br.ts` e `types.ts` no mesmo commit. Zero literal em JSX.
- Nenhum controle visível sem contrato funcional e sem estado de erro.
- Sem alteração em `main.ts` além de canais IPC estritamente necessários, cada um validando argumentos.
- Preservar CSP, `contextIsolation`, `sandbox`, preload nominal.

### 3.1 Sidebar

| Item | Substrato existente | Trabalho |
|---|---|---|
| **Nova tarefa** `Ctrl+N` | sessão nova | compor |
| **Início / Code** | — | novo alternador de modo |
| **Fixados** | — | novo, estado local |
| **Tarefas** (visão, filtro, criar) | Goal + `goals.max_turns` | listar sessões com Goal ativo |
| **Recentes** — workspace + caminho | workspace da sessão | compor |
| **Conversas** — ponto de estado + badge **"Ação necessária"** | `submit_pending` / `approval_required` em `tools/approval.py:3623-3641` | **maior valor da sidebar** |
| **Agenda** | cron + `omniroute-daily-health.py` | UI nova sobre backend existente |
| **Conhecimento** | `.hermes/knowledge/` — **só especificado, nunca implementado** | backend + UI |
| **Marketplace** | `hermes:plugin:installDesktop` + `themes/install.ts` | UI nova |
| Rodapé: conta, plano, **Atualizar**, medidor de uso, engrenagem | update existe; uso vem do F6 | compor |

**Aviso de honestidade:** *Conhecimento* é o único item da referência que o Hermes **não tem implementado**. As Knowledge Cards estão definidas em `references/knowledge-and-rules.md` e nunca saíram do papel. Ou implemente o backend, ou não coloque o item na sidebar. **Não crie um botão que abre uma tela vazia.**

### 3.2 Painel de tarefas em segundo plano
Do Claude Desktop. Lista de trabalho assíncrono com estado (`Em execução` / `Concluído`), duração, saída parcial, e ação de cancelar. Substrato: `delegate_task` já emite `subagent_stop` (`tools/delegate_tool.py:3453`), e o F2 (replay) já grava eventos por turno. Isto é a superfície visual daquilo.

### 3.3 Paleta `@` — overlay central
Primitivo: `components/ui/command.tsx`.

```text
Buscar contexto, plugins, agentes e mais
─────────────────────────────────────────────
Arquivos              → fs-ipc readDir (confinado por resolveAllowedFsIpcPath)
Pastas                → idem, diretório
Anexo                 → readFileDataUrlForAttach
─────────────────────────────────────────────
Plugins               → lista real do PluginManager, com estado
Agentes               → roster de references/multi-agent-orchestration.md (9 papéis)
Habilidades e comandos→ skills/ + slash commands
─────────────────────────────────────────────
[toggle] Spec  "Propor um plano primeiro e prosseguir após confirmação"
[toggle] Goal  "Definir um objetivo e trabalhar até concluir"
```

**O toggle Spec é o item de maior alavancagem da U1.** Ele já existe no backend: `/goal draft` produz o contrato e pausa com `paused_reason = "awaiting-spec-review"`; `/goal resume` libera. Hoje só existe como slash command e nenhum usuário leigo descobre.

Ligar o toggle = chamar o caminho `draft`. A UI renderiza o contrato com **Revisar** e **Construir**.

Ao implementar, corrija a divergência já auditada: o gateway pausa só para `draft`, o CLI pausa para qualquer contrato, e ambos usam `mgr.pause(...) or state` — que afirma "pausado" mesmo quando a pausa falhou. **Extraia uma função única para gateway, CLI e UI.**

### 3.4 Composer
```text
"Planeje e construa, @ para contexto, / para comandos"
[+] paleta · [Agente ▾] · [Modelo ▾ · Auto] · [🎤 voz] · [enviar]
```
Modelo vem de `omniroute_list_models_catalog`. Voz: existe hook `pre_transcription`. **Botão sem implementação não entra** — se "refinar prompt" não tiver backend, não desenhe o ícone.

### 3.5 Estado vazio
Três a quatro sugestões que **executam de verdade**, adaptadas ao workspace detectado. Sem workspace aberto, oferecer primeiro o seletor "Trabalhar em: <projeto>".

### 3.6 Estados obrigatórios
Para **cada** superfície: `loading`, `vazio`, `erro`, `offline`, `permissão negada`, `sucesso parcial`. Primitivos `empty-state.tsx` e `error-state.tsx` já existem. Todos em pt-BR.

---

## 4. DESIGN STUDIO — "fácil de mexer para leigos"

Este é um produto distinto do §3, e é o que responde ao pedido de *"layout e designer fácil de mexer para leigos construírem seus projetos"*.

**Distinção que precisa ficar clara:** §3 é a aparência **do Hermes**. §4 é a capacidade de o usuário leigo controlar a aparência **do projeto que ele está construindo** — sem escrever CSS.

### 4.1 Substrato já disponível
O commit `900234c` empacotou exatamente o arsenal necessário:
```text
skills/creative/design-toolkit/  frontend-design · ui-ux-pro-max · design
                                 banner-design · ui-designer · impeccable
skills/creative/gsap/            8 skills de animação (MIT, livre p/ comercial)
skills/creative/motion-design/   LottieFiles
skills/creative/img2threejs/     imagem → 3D
skills/creative/claude-design · design-md · architecture-diagram · baoyu-infographic
```
Mais: preview real via `<webview>`, Playwright no projeto, e o rail direita para diff.

### 4.2 A superfície
Um painel **Design** no rail direita, ativo quando o projeto em construção tem UI:

1. **Estilo** — escolha visual em linguagem de leigo, não de designer: *"Clean e profissional"*, *"Ousado e colorido"*, *"Minimalista"*, *"Escuro e técnico"*. Cada opção é um preset que o agente traduz em tokens no projeto do usuário.
2. **Cor da marca** — um seletor de cor. `themes/color.ts` e `accent-override.ts` já fazem derivação de paleta; reaproveite a lógica para gerar a escala completa a partir de uma cor, com contraste WCAG AA garantido.
3. **Tipografia** — três a cinco pares prontos. Nunca uma lista de 900 fontes.
4. **Densidade e cantos** — dois sliders. Compacto↔espaçoso, reto↔arredondado.
5. **Movimento** — desligado / sutil / expressivo. Mapeia para as skills GSAP e motion-design. **Respeitar `prefers-reduced-motion`** — o `styles.css` já tem o override global; o projeto gerado precisa herdar a mesma disciplina.
6. **Aplicar e ver** — muda o preview ao vivo. `Desfazer` sempre disponível.

### 4.3 Regras
- Toda alteração vira **código real no projeto do usuário**, versionado e no diff. Nunca um estado invisível.
- Contraste AA validado antes de aplicar; se a cor escolhida reprovar, ajustar e **avisar por quê**, em português claro.
- O usuário leigo nunca vê `--color-primary-500`. Vê "Cor da marca".
- O painel é opcional: quem sabe CSS edita o código direto, e o painel reflete.

---

## 5. ACESSIBILIDADE — contrato

O repositório **já impõe** parte disto. Não afrouxe:

- `components/ui/__tests__/no-native-title.test.ts` — proíbe `title` nativo. Use `aria-label` e tooltip próprio.
- `components/ui/keyboard-first.ts` — helper de navegação por teclado. Use.
- `styles.css` — `prefers-reduced-motion` já zera animação globalmente.

Acrescentar na U1: ordem de foco previsível, foco visível, navegação completa por teclado em sidebar/paleta/composer/rail, `aria-live` em indicadores que mudam de estado (incluindo "Ação necessária" e o indicador de contexto externo do F1), contraste AA em todos os skins — **valide os quatro presets, não só o `nous`**.

**Corrigir de passagem:** o chip "Acesso do agente ativo" em `preview-browser-bar.tsx:188-196` é texto fixo sem binding e desaparece abaixo do breakpoint `lg`. Vincule ao estado real e torne visível em toda largura.

---

## 6. i18N

- pt-BR do desktop está em **~18,2%** (≈449 de ≈2.463 chaves). Toda tela nova da U1 nasce 100% traduzida — o débito antigo é tratado à parte, mas **não se acrescenta débito novo**.
- O `web/` tem i18n próprio (21 arquivos). pt-BR precisa existir lá também.
- Teste de cobertura por locale que falha abaixo de 90% para idioma anunciado como suportado.

---

## 7. ACEITE DA U1

```text
Um usuário leigo, sem ler documentação, encontra e usa:
  Spec · Goal · Agentes · Habilidades · Agenda · Marketplace
  (Conhecimento só se o backend existir)

Aprovação pendente em sessão de segundo plano aparece como "Ação necessária"
Tarefas em segundo plano visíveis, com estado e cancelamento
Nenhum botão sem comportamento · nenhuma string fora do i18n
pt-BR 100% nas telas novas
Contraste AA nos 4 skins · navegação completa por teclado · sem `title` nativo
Sem regressão em CSP, contextIsolation, sandbox, preload
Design Studio altera o preview ao vivo e gera código real no diff
```

---

## 8. ANTES DE CODIFICAR

1. Ler `apps/shared/src/skin.ts` e decidir a forma final do token compartilhado.
2. Ler `components/ui/command.tsx` — a paleta `@` sai dali.
3. Ler `themes/install.ts` — o Marketplace de temas já resolve metade da tela de Marketplace.
4. Confirmar se `.hermes/knowledge/` tem qualquer implementação. Se não tiver, **decidir explicitamente**: implementar ou remover o item da sidebar.
5. Inventariar quais dos 349 componentes já cobrem a sidebar e o rail — o trabalho real da U1 pode ser muito menor do que parece.
