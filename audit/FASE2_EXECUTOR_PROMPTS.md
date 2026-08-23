# Fase 2 — Prompts prontos para o executor (Claude Code / Codex no SEU PC)

Estes são os itens que **não consigo executar** no meu ambiente de nuvem (sem toolchain
Windows, sem display, sem o stack de modelos em runtime). Cada bloco é auto-contido:
escopo, arquivos, NÃO FAZER, comandos de verificação. Rode no PC, no working tree do
projeto.

---

## EXECUTOR 1 — Rebuild Windows + prova de runtime do P0 (§6/§27)

**Objetivo:** provar que o boot loop do updater sumiu no app INSTALADO (não no dev).

**Contexto:** as correções de source do P0 (fork-guard + backoff + classificação de venv +
os 3 fixes fail-open desta entrega) estão em
`apps/desktop/electron/{main.ts,update-policy.ts,update-decision.ts,update-backoff.ts,venv-blocker-scan.ts}`.
O binário instalado `v0.20.4` é ANTIGO e NÃO contém o fix — não use ele como prova.

**Passos:**
1. `cd apps/desktop`
2. `npm ci`
3. Typecheck: `npx tsc -p tsconfig.electron.json --noEmit` e `npx tsc -p . --noEmit`
4. Testes: `npx vitest run --project electron` (esperado: ~1633 passed) e `--project ui`
5. Build + instalador Windows: `npm run dist:win` (ou o script de dist já existente — NÃO
   invente nome; veja `package.json`).
6. Instale a versão nova. **Confirme a versão** (Settings/Sobre) — NÃO valide na v0.20.4.
7. Prova de runtime (capture evidência de cada um):
   - cold start → backend chega a READY;
   - feche 100% (inclusive tray) → reabra → READY de novo; repita 3×;
   - simule o cenário de fork: garanta que o checkout está no fork (`git branch`), gateway
     segurando o venv → confirme no `%APPDATA%\...\logs\desktop.log`: `auto-update SKIPPED`
     e backend READY, **sem** `exited before it became ready`;
   - force uma falha de update (ex.: desconecte a rede no momento do handoff) → confirme
     backoff persistido em `%APPDATA%\...\update-backoff.json` e que o **próximo boot NÃO
     re-tenta** (vai direto ao backend).
8. `state.db`: `PRAGMA integrity_check;` = ok (não apagar nada).

**NÃO FAZER:** não rodar com `--force-venv`; não forçar update para `main`; não apagar
`state.db`/venv; não validar na v0.20.4; não declarar PASS sem os logs de READY×2.

**Verificação/entrega:** cole o SHA-256 do instalador, a versão, o resultado de vitest, e
os trechos de log provando READY após cold start e após restart. Só então:
`P0_UPDATER_STARTUP = RUNTIME_PASS`.

---

## EXECUTOR 2 — Fechar LOCAL_ONLY no egress auxiliar (§11) — FAIL hoje

**Objetivo:** em `local_only`, NENHUM caminho auxiliar (compression/title/vision/MoA/
oneshot/plugin_llm), fallback de falha/402, visão ou gen-tool pode enviar conteúdo para
provider não-loopback. Hoje só o loop principal é protegido.

**Causa raiz:** `agent/auxiliary_client.py` não consulta `authorize_route`. A política
correta e fail-closed já existe em `agent/local_only.py` (`LocalOnlyPolicy.authorize_route`).

**Arquivos:** `agent/auxiliary_client.py` (chokepoint `_call_llm_impl` ~9277 e
`async_call_llm` ~10099; fallback `_try_configured_fallback_for_unavailable_client` ~5709;
`resolve_vision_provider_client` ~7195), `agent/local_only.py`,
`agent/agent_init.py:1775` (onde a policy é construída de `security.local_only`),
`agent/auxiliary_client.py:3220` (ContextVar `_RUNTIME_MAIN_CONTEXT`).

**Abordagem sugerida (um único gate compartilhado, fail-closed):**
1. O loop principal já publica contexto no ContextVar `_RUNTIME_MAIN_CONTEXT`. Faça o
   `agent_init`/loop publicar também o flag `local_only` (bool) nesse contexto (ou um
   `LocalOnlyPolicy` imutável).
2. Em `_call_llm_impl` e `async_call_llm`, **imediatamente antes** de criar/usar o client,
   resolva o `provider`+`base_url` FINAIS e chame `authorize_route`. Se negado → **raise**
   (não silencioso). Se o contexto não trouxer local_only (retrocompat) → default permitir
   (sem mudança de comportamento) — mas quando o loop publicar local_only=true, bloquear.
3. Aplique o mesmo gate em `resolve_vision_provider_client` (o "auto" que vai p/ cloud) e
   nos gen-tools `tools/{image,video}_generation_tool.py`.
4. Troque o `authorize_tool` de **denylist** para **allowlist** de rede (ou, no mínimo,
   negue por padrão tools com capability de rede desconhecida em local_only).
5. `agent/account_usage.py`: não fazer POST a cloud em local_only (ou gate explícito).

**NÃO FAZER:** não quebrar o caminho loopback (ollama/lmstudio local devem continuar
funcionando); não afrouxar o gate do loop principal; não usar mock para "provar"
integração; não declarar PASS sem os testes abaixo verdes.

**Testes obrigatórios (adicione a `tests/agent/`):**
- local_only ON + auxiliar (compression/title/vision) apontando p/ base_url cloud → **raise
  BLOCKED**, nada enviado.
- local_only ON + falha do provider local → **NÃO** cai para cloud (sem fallback).
- local_only ON + `image_generate`/`video_generate` → negado.
- local_only OFF → tudo funciona como antes (retrocompat).
- **canary:** remova o gate do `_call_llm_impl` → os testes acima devem falhar.
Rodar: `python -m pytest tests/agent/test_local_only.py tests/agent/ -k "local_only or aux" -q`.

**Verificação/entrega:** cole o resultado do pytest (com o canary provando mordida). Só
então: `LOCAL_ONLY = PASS`.

---

## EXECUTOR 3 (menor) — 2×P1 de Electron + P2 do updater

**P1-a (token em URL):** parar de mandar o token do gateway ao renderer/URL. Mover
`media.ts:126` e `api/plugins.ts:95` para header `Authorization`; manter o token no main
(cunhar por-uso como o ticket de WS). Arquivos: `apps/desktop/electron/main.ts:12463`,
`src/lib/media.ts`, `src/api/plugins.ts`, `src/global.d.ts:704`.

**P1-b (leitura fs não-scoped):** `readFileText/readFileDataUrl/readFile*ForAttach`
(`main.ts:14142+`) devem usar `resolveAllowedFsIpcPath` (allowed-roots) como a escrita, não
só o denylist de `hardening.ts:377`.

**P2 updater:** (1) lock exclusivo (`wx`/O_EXCL) antes do primeiro passo destrutivo em
`applyUpdates` (TOCTOU cross-process); (2) `recordUpdateFailure`+persist nos returns de
`main.ts:~3799` (holder externo) e `~3978` (spawn-failed); (3) em
`update-backoff.ts:parseBackoffState`, arquivo presente porém corrompido → janela de
backoff conservadora em vez de `INITIAL`.

**Verificação:** vitest electron verde + canaries novos para cada proteção.
