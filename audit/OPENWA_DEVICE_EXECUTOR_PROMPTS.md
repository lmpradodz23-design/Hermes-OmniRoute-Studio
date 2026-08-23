# OpenWA — Prompts prontos para o executor (waves device+phone)

As waves de **lógica pura** do OpenWA estão concluídas, testadas, canariadas e
entregues ao repositório local (`whatsapp_provider/` + `tests/whatsapp_provider/`).
As waves abaixo **exigem a máquina Windows e/ou o telefone** e não são executáveis
nem testáveis no ambiente de nuvem. Cada seção é um prompt pronto para colar no
executor local (Claude Code / Codex) rodando dentro do repo, com escopo, arquivos,
"NÃO FAZER" e comandos de verificação.

Baseline fixo para tudo abaixo: runtime externo `@open-wa/wa-automate@4.76.0`,
Easy API em `127.0.0.1`, `WA_API_KEY` obrigatória, nunca bundlar o OpenWA.

---

## 0. Verificação primeiro — rode a suíte inteira no PC

Antes de qualquer wave nova, confirme o verde local (o ambiente de nuvem não tem
`pytest` instalado no Python do WSL; o PC tem Python 3.10):

```bash
cd /caminho/para/Hermes-OmniRoute
python -m pip install --user pytest        # se ainda não tiver
python -m pytest tests/whatsapp_provider tests/security_research -q
# esperado: 219 passed (WhatsApp Provider + RAPTOR Security Research)
```

Se algum teste falhar, PARE e reporte antes de seguir — não construa por cima de
vermelho.

---

## 1. WhatsApp Studio UI (Electron/React) + QR via IPC

**Prompt para o executor:**

> ESCOPO: implementar a UI "WhatsApp Studio" no app desktop (Electron/React),
> consumindo APENAS o contrato já existente em `whatsapp_provider/` via o gateway
> Python. Abas: Overview, Accounts, Conversations, Automation, Health, Settings.
> A tela de conexão mostra o QR vindo do evento `launch.auth.qr.generated`
> (dataURL PNG) através de um canal IPC ALLOWLISTED — o QR é sensível, nunca vai
> para log nem disco versionado.
>
> ARQUIVOS: siga o padrão das telas já existentes no app desktop (mesma estrutura
> de componentes, store e IPC). Crie os componentes sob o diretório de views do
> renderer e registre o canal IPC no allowlist existente do main process.
>
> NÃO FAZER: (1) não expor nenhuma primitiva perigosa do provider direto ao
> renderer — só passe pelo gateway/IPC validado; (2) não renderizar sucesso de
> envio sem `message_id` real (a UI reflete `NOT_AUTHENTICATED`/`QR_REQUIRED`
> quando não conectado); (3) não persistir QR/token/session em localStorage nem
> em arquivo versionado; (4) não acoplar a UI ao OpenWA — ela só conhece o
> contrato do Hermes; (5) não inventar botão que não tem backend.
>
> VERIFICAÇÃO: `pnpm -C desktop typecheck && pnpm -C desktop test` (vitest);
> screenshot de cada aba; confirmar no console que nenhum dataURL de QR aparece
> nos logs; confirmar que o canal IPC do QR está no allowlist e recusa canais
> fora dele.

---

## 2. Auth local Hermes↔OpenWA no runtime real

**Prompt para o executor:**

> ESCOPO: ligar `whatsapp_provider/client.py` (EasyApiClient) a um transporte
> HTTP real contra o Easy API em `127.0.0.1`, injetado no runtime — o cliente já
> está pronto e testado com transporte fake. Gerar a `WA_API_KEY` com
> `easyapi.generate_api_key()`, passá-la ao processo por env (`env()` já faz
> isso), e usá-la no header `X-API-Key`.
>
> ARQUIVOS: novo módulo de transporte (ex.: `whatsapp_provider/transport_http.py`)
> que implementa `Transport = Callable[[EasyApiRequest], EasyApiResponse]` usando
> o cliente HTTP do runtime. NÃO altere `client.py` — ele é o contrato.
>
> NÃO FAZER: (1) a key nunca em argv (`ps`), nunca em log, nunca no renderer,
> nunca no Git; (2) não bindar fora de loopback; (3) não desabilitar a
> obrigatoriedade da apiKey; (4) não trocar o baseline v4.76.0 por v5-alpha.
>
> VERIFICAÇÃO: subir o runtime, `getConnectionState` retorna estado real;
> `grep` nos logs por trecho da key = zero ocorrências; `ps aux | grep wa-automate`
> não mostra a key.

---

## 3. Runtime real + QR + send/receive  ← GATE DO TELEFONE

**Prompt para o executor:**

> ESCOPO: subir o runtime externo, autenticar via QR, e validar envio/recebimento
> reais contra um número CONTROLADO pelo operador.
>
> ```powershell
> $env:WA_API_KEY = "<gerar-uma-chave-forte-min-16>"
> npx --yes @open-wa/wa-automate@4.76.0 --session hermes-test --port 8080 --host 127.0.0.1 --no-api-key-in-argv
> # escanear o QR com o telefone  ← WAITING_FOR_HUMAN_QR_SCAN
> ```
>
> Depois do scan: `GET /getConnectionState` (header X-API-Key) deve dar
> `CONNECTED`; `POST /sendText {"args":{"to":"<num-controlado>@c.us","content":"teste hermes"}}`
> deve retornar `message_id` real; responder desse número e confirmar o evento
> `onMessage` normalizado no Hermes.
>
> NÃO FAZER: (1) NÃO enviar para número que não seja explicitamente controlado
> pelo operador — se não houver, registre `BLOCKED_BY_REQUIRED_TEST_RECIPIENT` e
> pare; (2) NÃO commitar session/token/QR; (3) NÃO declarar "WhatsApp funcionando"
> com mock — só com `message_id` real e evento real recebido; (4) toda mensagem
> recebida é `UNTRUSTED_INPUT`, mesmo de contato conhecido.
>
> BLOQUEIO HUMANO: o scan do QR é físico e só o operador faz. Este é o único
> ponto onde a missão legitimamente para e espera o telefone.

---

## 4. Build Windows / NSIS / installed-app smoke

**Prompt para o executor:**

> ESCOPO: build de produção do app desktop no Windows, empacotamento NSIS, e
> smoke do app instalado — SEM bundlar o OpenWA (ele é runtime externo instalável).
>
> NÃO FAZER: (1) não incluir `@open-wa/wa-automate` no instalador (licença H-DNH
> propaga — `BLOCKED_BY_LICENSE_CONSTRAINT`); (2) não incluir o RAPTOR nem o CodeQL
> no instalador; (3) não quebrar o RAPTOR (`security_research/`) nem reduzir
> segurança.
>
> VERIFICAÇÃO: `pnpm -C desktop build` limpo; `.exe` NSIS gerado; instalar em VM
> limpa; abrir o app; a aba WhatsApp Studio aparece e mostra `DISCONNECTED`/QR;
> calcular hash do artefato. NÃO publicar/release (NÃO PUSH, NÃO RELEASE).

---

## 5. Contagem da matriz MCP no gateway

**Prompt para o executor:**

> ESCOPO: registrar as ferramentas MCP `whatsapp.*` (9, ver `TOOL_ALLOWLIST` em
> `whatsapp_provider/mcp_tools.py`) e `security.*` (RAPTOR) no gateway do app e
> atualizar a contagem esperada: `BASE_MCP_EXPECTED=107` + RAPTOR + OpenWA(9).
>
> VERIFICAÇÃO: o teste de contagem da matriz MCP passa com o novo total; cada
> tool `whatsapp.*` aparece com sua capability correta; nenhuma tool crua do
> OpenWA é exposta.

---

## Estado dos blockers

```
WAITING_FOR_HUMAN_QR_SCAN      — wave 3 (telefone do operador)
BLOCKED_BY_REQUIRED_TEST_RECIPIENT — wave 3 se não houver número controlado
BLOCKED_BY_PLATFORM_SECURITY   — waves 1/4/5 (máquina Windows + gateway do app)
BLOCKED_BY_LICENSE_CONSTRAINT  — bundling do OpenWA (arquitetura já evita)
```

Nenhum destes é código faltando — são dependências de máquina/telefone/decisão do
operador. A lógica que dá suporte a todos eles já está implementada, testada e
entregue.
