# OpenWA Integration Report

## Executive summary

O OpenWA (`@open-wa/wa-automate`) foi auditado e a fundação da sua integração ao
Hermes OmniRoute Studio foi implementada como um WhatsApp Provider desacoplado e
testável. A licença H-DNH e a imaturidade do v5-alpha determinaram a
arquitetura: **runtime externo (Easy API), v4.76.0 estável, apiKey obrigatória,
bind 127.0.0.1**. O domínio Python (sessão, eventos, envio, validação, config)
tem 51 testes com canários. O que exige telefone/Windows (QR real, send/receive
E2E, UI, packaging) está registrado como `WAITING_FOR_HUMAN_QR_SCAN` /
device-required — não como concluído.

## Upstream version

commit 56102e6, branch master = v5.0.0-alpha. Baseline operacional escolhida:
**4.76.0** (npm `latest`).

## Architecture

`Hermes → WhatsAppService → WhatsAppProvider → OpenWAProvider → OpenWA runtime externo`.
Baixo acoplamento; o core só conhece a interface. Ver
`docs/OPENWA_INTEGRATION_ARCHITECTURE.md`.

## License

H-DNH (Hippocratic + Do No Harm) — propagação + restrições de uso →
`BLOCKED_BY_LICENSE_CONSTRAINT` para bundling → runtime externo instalado pelo
usuário. Ver `docs/OPENWA_LICENSE_AUDIT.md`.

## V4/V5 decision

v4.76.0 (estável) como baseline; v5-alpha tem 17 métodos `unsupported`, listeners
0/30 e mídia 0/40 migrados — o próprio README manda manter produção no v4. A
interface permite trocar quando v5 amadurecer.

## Runtime / Browser

Easy API como processo separado (crash containment + licença). Puppeteer é o
driver default do OpenWA; browser fora do processo Electron.

## Session / QR

Máquina de estados honesta (`CONNECTED` sem conexão fingida). QR é evento
`launch.auth.qr.generated` (dataURL PNG, marcado sensível). Persistência via
perfil do Chromium (`_IGNORE_{sessionId}`), fora do git.

## Messaging / Events

Envio: `SENT` só com o MessageId real. Eventos normalizados para contrato
estável, dedup por `message.id`, toda mensagem `untrusted`.

## MCP / Agents / Memory / Cron

Pendente (Wave 6-7): expor `whatsapp.status/sessions/send_text/send_media/
get_chats/get_messages` como ferramentas MCP no gateway, por allowlist (não a
API bruta inteira). As 107 ferramentas MCP existentes e as do RAPTOR não foram
tocadas.

## Security

Mensagem = entrada não confiável; anti-loop; rate-limit por sessão; validação de
ID/texto/mídia (path traversal reusa a fronteira do RAPTOR); allowlist de
browser args; apiKey obrigatória por env; log redigido. Tudo com teste.

## Tests

`whatsapp_provider/`: 51/51 passed. Canários confirmam que SENT-sem-id e
host-não-loopback reprovam quando a defesa é desfeita. Regressão do Hermes: OpenWA
é aditivo; RAPTOR e o fix-loop intactos.

## Performance

NOT_MEASURED (exige runtime real no Windows).

## Packaging

OpenWA NÃO entra no instalador (licença). Instalado pelo usuário via `npx`. O
Hermes distribui só o adapter.

## Blockers

`OPENWA-LIC-1` (bundling), `OPENWA-QR-1` (WAITING_FOR_HUMAN_QR_SCAN),
`OPENWA-DEVICE-1` (UI/packaging/E2E/runtime real). Ver checkpoint.

## Git state

Ver `git status` na entrega. DO_NOT_PUSH / DO_NOT_RELEASE. Commit anterior de
auditoria e RAPTOR preservados.
