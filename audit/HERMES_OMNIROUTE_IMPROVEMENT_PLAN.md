# HERMES OMNIROUTE — PLANO DE MELHORIA

Classificação: `MUST_FIX` (bloqueia release) · `SHOULD_FIX` (define o produto) · `NICE_TO_HAVE`.

Regra que governa tudo abaixo: **preservar o que funciona.** O empacotamento, a identidade lado-a-lado, o hardline floor, o isolamento de canal do `_smart_approve`, o `execute_code` em subprocesso e o modelo de preload com API nominal são bons. Nenhuma proposta aqui os remove.

---

## PARTE A — Arquitetura e integridade

### A1. Desacoplar o Studio do runtime do Hermes original — `MUST_FIX`
Hoje o Studio escreve plugin, bridge e script dentro de `ACTIVE_HERMES_ROOT` (HERMES-010). Criar `HERMES_HOME/omniroute-studio/{plugins,integrations,scripts,skills}` e registrar esse diretório como fonte adicional de descoberta no backend, em vez de escrever no runtime compartilhado. Ganho: o Hermes original volta a ser realmente preservado, a desinstalação fica possível e o upgrade deixa de ser destrutivo.

### A2. Modelo de permissão por capacidade para o MCP — `MUST_FIX`
Substituir o enforcement auto-concedido (HERMES-003) por um modelo real:
- conjunto default mínimo (6 escopos de leitura + `execute:completions`);
- consentimento por **categoria** na UI ("Permitir que o agente use suas notas do Obsidian?"), com estado persistido e revogável;
- `write:plugins`, `write:skills`, `execute:skills` exigem consentimento explícito e individual, sempre, com texto que explique que isso é execução de código;
- quando houver transporte HTTP autenticado no OmniRoute, derivar escopos do token e ignorar a env.

Isso reduz a superfície default de 106 ferramentas para ~20 **sem remover funcionalidade** — apenas exigindo ativação consciente.

### A3. Plugin `security_critical` com fail-closed — `MUST_FIX`
Novo campo no manifesto. Para plugins assim: falha de carga aborta o start com mensagem acionável; exceção num hook **bloqueia** a chamada em vez de liberá-la (HERMES-014, HERMES-015). Resolve a classe inteira de "proteção ausente e silenciosa".

### A4. Registry de bridge MCP com integridade — `MUST_FIX`
A bridge deixa de descobrir código por env var (HERMES-002): allowlist de raízes gravada na instalação, `realpath` canônico, verificação de nome e faixa de versão do pacote, consumo de `dist/` compilado em vez de `tsx` em runtime. Preferencialmente migrar para o transporte HTTP autenticado que o próprio OmniRoute já expõe (`httpTransport.ts`).

### A5. Marcação de proveniência de conteúdo — `SHOULD_FIX` (e é o que mais diferencia o produto)
Todo texto que entra no contexto vindo de web, arquivo, memória, resposta MCP ou skill instalada recebe um envelope de origem, e o system prompt instrui explicitamente que conteúdo `untrusted` nunca é instrução. O produto já faz isso corretamente num lugar (`_smart_approve`, canal system × `<command>`); generalizar esse padrão é a maior melhoria de segurança disponível e nenhum concorrente direto faz bem.

### A6. Audit trail unificado — `SHOULD_FIX`
Hoje há três trilhas desconexas: `logToolCall` do MCP, relatório de tarefa do guardrail e logs do Electron. Unificar num log append-only por sessão com: ferramenta, argumentos redigidos, veredito de aprovação, origem do conteúdo que motivou a chamada, exit code e custo. É a base de tudo em A5 e do que o usuário precisa para confiar em execução autônoma.

### A7. Circuit breaker, cancelamento e limites de recurso — `SHOULD_FIX`
`delegation.max_concurrent_children: 5` e `max_spawn_depth: 2` existem mas não têm teste. Adicionar: cancelamento propagado a filhos, timeout por delegado com resultado `PARTIAL` honesto, circuit breaker por provedor e teto de custo por sessão vinculado ao `omniroute_set_budget_guard` (que hoje o próprio agente pode desligar).

### A8. Checkpoints e tarefas retomáveis — `NICE_TO_HAVE`
Goal já tem `pause`/`resume`. Estender para checkpoint de estado de workspace (snapshot de diff) permitindo retomar após crash sem repetir trabalho.

---

## PARTE B — O que você pediu diretamente

### B1. Catálogo de provedores com base URL pré-preenchida — `SHOULD_FIX`
**Hoje:** `PROVIDER_GROUPS` (`constants.ts`) tem `prefix`, `name`, `description`, `docsUrl`, `priority` — **não tem `baseUrl`**. O usuário precisa colar a URL de cada provedor à mão.

**Proposta concreta:**
```ts
// apps/desktop/src/app/settings/provider-presets.ts (novo)
export interface ProviderPreset {
  id: string
  name: string
  baseUrl: string            // pré-preenchido, editável
  defaultModel?: string
  keyEnvVar: string
  keyPlaceholder: string     // formato esperado, sem exemplo real
  docsUrl: string
  auth: 'api-key' | 'oauth-pkce' | 'device-flow'
}
```
Na UI: um seletor de provedor que preenche URL e modelo, deixando **apenas o campo de chave vazio**, com botão "usar padrão" / "sobrescrever URL". Cobre Vercel AI Gateway, Xiaomi MiMo, OpenRouter, Groq, Together, DeepSeek, Fireworks, Cerebras, Mistral, Ollama local, LM Studio local, e os que já existem no `config_defaults.py`.

### B2. Login sem colar chave — `SHOULD_FIX`, com um limite explícito
**Não é possível, e não deve ser tentado:** usar assinatura Claude ou ChatGPT dentro do Hermes. A Anthropic bloqueou tecnicamente harnesses de terceiros em assinaturas Claude em 2026; a OpenAI trata o login do ChatGPT como client de primeira parte. Raspar cookie da sessão web é circumvention, quebra sozinho e leva a banimento de conta. **Isto não entra no produto.**

**O que é possível e resolve o mesmo problema de ergonomia:**
1. **Sign in with OpenRouter (OAuth PKCE)** — fluxo oficial para apps de terceiros. Um login no navegador entrega uma chave ao app sem que o usuário cole nada, e dá acesso a Claude, GPT, Gemini, Llama, DeepSeek e centenas de modelos por um provedor só. **É a resposta certa.** O Hermes já tem toda a infraestrutura: `native-oauth.ts` implementa PKCE (`challenge`, `redirectUri`, `state`), `native-token-store.ts` persiste tokens e `safeStorage` os protege.
2. **GitHub Copilot device flow** — client público para editores.
3. **Google/Gemini OAuth**, **AWS Bedrock** e **Azure OpenAI** via SSO corporativo.
4. Todas as credenciais em `safeStorage`, num painel **"Contas"** único, com estado (conectado/expirado/revogado) e botão de desconectar — substituindo o formulário técnico atual.

### B3. Painel principal no estilo Qoder/Quest — `SHOULD_FIX`, escopo delimitado
**Não é redesign livre.** Especificação para o Codex:

- **Sidebar esquerda persistente:** ação primária "Nova tarefa" com atalho visível; seção Fixados; seção Tarefas com filtro e agrupamento; seção Chats recentes com estado por item (rodando / requer ação / concluído); rodapé com conta, uso e configurações.
- **Área central em estado vazio:** título curto, seletor de escopo ("Trabalhar em: <projeto>"), composer grande com dicas inline (`@` para contexto, `/` para comandos), e **3–4 sugestões acionáveis** que executam de verdade — não texto decorativo. Ex.: "Criar um app de lista de tarefas", "Elevar a cobertura de testes deste projeto", "Auditar segurança deste repositório".
- **Composer:** seletor de agente, seletor de modelo (Auto por padrão), anexo, voz.
- **Rail direita:** preview, terminal, arquivos, diff — os que já existem, organizados.
- **Estados obrigatórios:** loading, vazio, erro, offline, permissão negada, sucesso parcial. Cada um em pt-BR.
- **Restrição:** reutilizar os primitivos existentes (`SectionHeading`, `Pill`, `EmptyState`, `Codicon`, tokens de tema). Nenhuma biblioteca de UI nova. Nenhuma mudança em `main.ts`.

### B4. pt-BR completo — `MUST_FIX` para o público declarado
Ver HERMES-017. Meta: ≥90% das chaves, com teste de cobertura que falha abaixo do limiar. Prioridade: aprovações e segurança primeiro.

---

## PARTE C — "Melhor que Codex, Lovable, Qoder e Claude"

Observação honesta antes das ideias: **o Hermes OmniRoute não vence por ter mais recursos.** Ele já tem mais superfície que qualquer um deles — 106 ferramentas MCP, delegação, memória, SSH, preview, cron. O que ele não tem é *confiabilidade demonstrável*. O diferencial defensável está aqui:

### C1. Evidência verificável em vez de alegação — `SHOULD_FIX`
Nenhum concorrente entrega, ao fim de uma tarefa, um artefato assinado dizendo: estes arquivos mudaram, estes comandos rodaram, com estes exit codes, estas ferramentas foram usadas, este conteúdo externo entrou no contexto, este foi o custo. O relatório de tarefa do guardrail é o embrião disso — hoje quebrado (HERMES-006, HERMES-020, HERMES-031). Consertado e ampliado com A6, vira **a** razão para escolher este produto para trabalho autônomo.

### C2. Roteamento multi-modelo com política, não só failover — `SHOULD_FIX`
O OmniRoute já roteia. Falta política visível ao usuário: teto de custo por tarefa, "usar modelo gratuito para exploração e modelo forte para o diff final", degradação anunciada em vez de silenciosa (`degraded_reference_policy: 'loud'` já está no preset — expor isso na UI). Nenhum concorrente de assinatura fechada pode oferecer isso.

### C3. Execução local com fronteira real — `SHOULD_FIX`
Lovable e Vercel rodam na nuvem deles. Codex e Claude Code rodam na sua máquina mas com modelo de permissão grosso. O Hermes pode oferecer o meio termo que ninguém oferece: local, com capacidades declaradas por tarefa, revogáveis, auditadas. Depende de A2, A3, A5.

### C4. Orquestração multi-agente com contrato — `NICE_TO_HAVE`
`references/multi-agent-orchestration.md` já descreve roster, topologia e contrato de delegação com qualidade acima da média. Falta torná-lo executável: `delegate_task` com schema de retorno validado, ownership de arquivo aplicado (não sugerido) e reconciliação do diff combinado pelo orquestrador.

### C5. Onboarding de usuário leigo que realmente entrega — `SHOULD_FIX`
`references/nontechnical-intake.md` está bem escrito. Torná-lo real: um fluxo de primeiro uso que pergunta no máximo três coisas de negócio, detecta runtimes instalados, escolhe stack sozinho, e entrega uma fatia vertical funcionando com preview aberto. Isso é o que Lovable faz bem e é onde o Hermes pode competir sem depender da nuvem de ninguém.

### C6. Modo "prova de trabalho" — `NICE_TO_HAVE`
Um toggle que faz o agente rodar sempre com: verificação obrigatória, evidência anexada, e recusa de declarar conclusão sem exit code real. É a materialização de C1 e o oposto exato do que os 1.549 testes atuais fazem.

---

## PARTE D — Prioridade sugerida (custo × impacto)

```text
1. HERMES-041 (backup do trabalho)     — minutos, risco de perda total
2. A3 + HERMES-001 (guardrail carrega) — horas, desbloqueia toda a segurança
3. HERMES-005/006/007/008/024          — horas, corrige o que o guardrail deveria fazer
4. A2 + HERMES-003 (escopos MCP)       — dias, remove a maior superfície
5. A4 + HERMES-002 (bridge)            — dias, remove o RCE
6. HERMES-004 + HERMES-013 (Electron)  — dias, fecha renderer→host
7. B4 pt-BR                            — dias, o produto passa a existir para o público
8. B1 + B2 (presets + OAuth)           — dias, resolve a ergonomia que você pediu
9. A5 + A6 + C1 (proveniência+trilha)  — semanas, é o diferencial real
10. B3 (painel)                        — semanas, depois que o resto for confiável
```
