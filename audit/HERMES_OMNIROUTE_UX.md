# HERMES OMNIROUTE — AUDITORIA DE UX/UI E pt-BR

**Limite de prova:** o aplicativo instalado **não foi executado** (ambiente Linux, app Windows). Tudo abaixo vem de leitura de código e medição de catálogos. Screenshots: `NOT_TESTED`. Acessibilidade em runtime, contraste renderizado, foco e navegação por teclado: `NOT_TESTED`.

## 1. pt-BR — o achado dominante

```text
en        ~2452 chaves   referência
zh        ~2613          107%
zh-hant   ~2127           87%
ja        ~2104           86%
ar        ~1927           79%
pt-br      ~380           15%   ←
```

`defineLocale` faz merge sobre `en`, então tudo que falta aparece **em inglês, sem aviso**. Para um produto que se define como *"designed for nontechnical users"* brasileiros, isso significa que a maior parte da interface — configurações, erros, diálogos, onboarding — chega no idioma que o usuário não domina.

O que o catálogo pt-BR **cobre bem**: `common`, o painel OmniRoute novo, `customEndpoints`, e as strings de preview. É um bom começo, não um catálogo de produto.

**Prioridade de tradução recomendada** (nesta ordem, por impacto):
1. Diálogos de aprovação e mensagens de segurança — inglês aqui é ativamente perigoso: o usuário aprova o que não entendeu.
2. Erros e estados de falha.
3. Onboarding e primeiro run.
4. Configurações (todas as abas).
5. Estados vazios e loading.
6. Notificações e tooltips.
7. Menus nativos e atalhos.

## 2. Indicador de segurança falso

`preview-browser-bar.tsx:188-196` renderiza um chip com ícone de escudo e o texto fixo "Acesso do agente ativo". Não há prop, estado ou condição. Além disso: `className="hidden … lg:flex"` — some abaixo do breakpoint `lg`.

Dois problemas de produto num só componente: um indicador que sempre diz a mesma coisa treina o usuário a confiar num sinal vazio; e o sinal desaparece justamente quando a janela está estreita. (HERMES-018)

## 3. Botões e fluxos — verificação de "botão clicável ≠ fluxo funcionando"

| Elemento | Backend real? | Observação |
|---|---|---|
| "Verificar conexão" (OmniRoute) | ✔ | `validateCustomEndpoint` real |
| "Configurar OmniRoute" | ✔ | grava config real — mas sobrescreve chaves do usuário sem avisar (HERMES-021) |
| Switch do Caveman | ✔ | IPC → bridge → CLI real; desabilita corretamente quando indisponível |
| Chip "Acesso do agente ativo" | ✗ | **estático** |
| Pills "Online/Offline/Configurado" | ✔ | refletem estado real |
| "N modelos disponíveis" | ✔ | do probe real |

Nenhum botão falso encontrado além do chip. Esta parte da integração é honesta.

## 4. Problemas de UX identificados no código

1. **Re-probe ao trocar de idioma.** `useEffect(..., [endpointCopy.loadFailed])` (`custom-endpoints-settings.tsx:163`) — mudar o idioma dispara novamente o carregamento de endpoints e o probe do OmniRoute. Efeito colateral invisível e desnecessário.
2. **"Configurar OmniRoute" não mostra o que vai mudar.** Reescreve delegação, goals, aprovações, memória, MoA e segurança. Um diálogo de confirmação com o diff seria o mínimo, dado que `approvals.mode` muda para `smart`.
3. **Sem feedback quando o controlador de compressão não existe.** `handleCavemanToggle` faz `return` silencioso se `window.hermesDesktop.omniRouteCompression` for undefined. O Switch fica desabilitado, o que mitiga — mas o texto "OmniRoute CLI is unavailable on this device" não explica o que fazer.
4. **Erro do toggle não traduzido no caminho `set`.** A exceção da bridge sobe crua (HERMES-027).
5. **Base URLs não pré-preenchidas.** O painel de endpoints exige colar URL manualmente para cada provedor. Existe um catálogo de provedores (`constants.ts:PROVIDER_GROUPS`) com `docsUrl` — não com `baseUrl`. É a lacuna que o usuário levantou diretamente e está no plano de melhoria.
6. **Estado dos bundles gerenciados invisível.** Se o guardrail ou o bridge não instalarem, só o console sabe (HERMES-009).
7. **Estado do guardrail invisível.** Não há tela que diga se a proteção está ativa. Dado HERMES-001, o usuário acredita estar protegido e não está.

## 5. "Isto parece um produto ou componentes adicionados ao Hermes?"

Resposta honesta: **componentes bem-feitos adicionados ao Hermes**, ainda não um produto coeso.

Sinais de coesão real: identidade completa e consistente (appId, executável, protocolo, ícone, versão PE, títulos, instalador); o painel OmniRoute segue os primitivos de UI existentes (`SectionHeading`, `Pill`, `EmptyState`); a documentação é séria e assume limites.

Sinais de colagem: OmniRoute mora dentro de "Custom Endpoints" — um lugar técnico, não o lugar onde alguém procura "meu roteador de IA"; Product Studio existe como skill em disco, sem nenhuma superfície de UI própria; Goal só existe como slash command; memória tem duas implementações concorrentes; Caveman é um switch solto dentro do painel de endpoints; não há uma tela que apresente o Studio como um todo.

Um usuário leigo que abrisse o app hoje não descobriria Product Studio, Goal, memória ou guardrails sem ler a documentação.

## 6. Acessibilidade — o que dá para dizer do código

Positivo: `aria-label` adicionado no botão de excluir endpoint (substituindo `title`), `aria-label` no Switch do Caveman, `role="status"` no chip.

Não verificável estaticamente e portanto `NOT_TESTED`: contraste real, ordem de foco, navegação por teclado no painel novo, anúncio por leitor de tela das mudanças de estado (o `role="status"` sem `aria-live` e com texto constante não anuncia nada), comportamento com zoom e em janela estreita.

## 7. Recomendação de redesign — **não executar nesta rodada**

Registrado para o Codex, na Wave 9, com escopo delimitado. Ver `HERMES_OMNIROUTE_IMPROVEMENT_PLAN.md` §UI.
