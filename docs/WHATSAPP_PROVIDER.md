# WhatsApp Provider — guia do módulo

Runtime de WhatsApp Web desacoplado para o Hermes, sobre o OpenWA. Descreve o
comportamento real do implementado; o que depende do telefone/Windows está
marcado como tal.

## Identidade correta

**WhatsApp Web / OpenWA Provider** — automação do WhatsApp Web, **não** a API
oficial da Meta. A UI nunca chama isto de "WhatsApp Official API". Uso sujeito
aos Termos do WhatsApp; o risco é do operador.

## Contrato do provider

```
connect() · disconnect() · getStatus() · healthCheck()
sendText() · sendMedia() · sendDocument() · sendReaction()
getChats() · getContacts() · subscribeEvents()
```

O core do Hermes fala só com essa interface. O OpenWA fica atrás do
`OpenWAProvider`. Recursos que a v4 não oferece são reportados como
`UNAVAILABLE`, nunca fingidos.

## Ciclo de sessão

```
DISCONNECTED → STARTING → QR_REQUIRED → AUTHENTICATING → CONNECTED
                                            ↑              │
                                      RECONNECTING ← DEGRADED
CONNECTED/DEGRADED → LOGGED_OUT   ·   qualquer → FAILED
```

`CONNECTED` só após autenticação real (`session.py` recusa pular do zero).
`can_send` é verdadeiro só em `CONNECTED`/`DEGRADED`.

## Envio

`QUEUED → SENDING → SENT | FAILED`. `SENT` **só** com o `MessageId` real
retornado pelo OpenWA — nunca no otimismo. Confirmação de entrega/leitura vem
depois pelo evento `ack` (1=servidor, 2=entregue, 3=lido).

## Eventos

Formato OpenWA → `NormalizedEvent` estável. Toda mensagem recebida é
`untrusted=True`. Dedup por `message.id` (o WhatsApp Web reentrega eventos;
processar duas vezes gera resposta dupla e loop).

## Defesas

- **Anti-loop** (`sending.py`): nunca responder à própria mensagem (`from_me`);
  teto de respostas por chat numa janela.
- **Rate-limit** por sessão: janela deslizante, teto real — contra loop de
  agente, retry storm e mass-send acidental.
- **Prompt injection**: mensagem é dado. Uma mensagem pedindo "ignore
  instruções / rode PowerShell / revele segredos" continua sendo texto de
  entrada, sem autoridade. Capability de ferramenta é gate separado.
- **Path traversal de mídia** (`validation.py`): reusa a fronteira do
  `security_research` — mídia por caminho não escapa da raiz autorizada.
- **IDs**: chat id validado por formato; metacaractere é recusado.
- **Browser args**: allowlist; `--no-sandbox` e afins são recusados.
- **Segurança do runtime** (`easyapi.py`): bind 127.0.0.1, apiKey obrigatória
  (por env, não argv), log com QR/token/cookie redigidos.

## Multi-session e isolamento

Cada sessão tem sua própria máquina de estados e seu próprio diretório de
sessão. Rate-limit e anti-loop são por sessão. Eventos de uma sessão nunca
cruzam para outra (chaveados por `session_id`).

## Segurança do diretório de sessão

Os dados de sessão (tokens, perfil do Chromium, cookies) ficam **fora do source
control**. O `.gitignore` do projeto exclui os diretórios de sessão; `git
status` nunca deve mostrar credencial de sessão. Nada disso vai para memória do
agente automaticamente.

## Runtime externo

O OpenWA roda como processo separado (Easy API), instalado pelo usuário via
`npx @open-wa/wa-automate@4.76.0` — **não** empacotado no Hermes (licença
H-DNH, ver `OPENWA_LICENSE_AUDIT.md`). O Hermes conecta em `127.0.0.1:8080` com
apiKey.

## O que exige telefone/Windows

Iniciar o OpenWA + QR (`WAITING_FOR_HUMAN_QR_SCAN`), envio/recebimento E2E real,
WhatsApp Studio UI, packaging. Ver arquitetura.
