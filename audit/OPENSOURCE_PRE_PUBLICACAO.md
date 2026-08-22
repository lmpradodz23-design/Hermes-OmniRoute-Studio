# Checklist de pré-publicação — Hermes OmniRoute Studio

Tudo aqui é **bloqueante**: tornar um repositório público é irreversível, e cada
item abaixo é uma coisa que não dá para desfazer depois.

---

## 🔴 P0-1 — `origin` aponta para o repositório do upstream

```
$ git remote -v
origin  https://github.com/NousResearch/hermes-agent.git (fetch)
origin  https://github.com/NousResearch/hermes-agent.git (push)
```

**A URL de push é a do upstream.** Não existe remote do fork configurado. Um
`git push` distraído — seu, de uma IDE, de um script, de um agente — tenta
escrever no repositório da Nous Research. Vai falhar por falta de permissão,
provavelmente. "Provavelmente" não é uma garantia de segurança.

Pior: enquanto `origin` for o upstream, **não existe lugar para publicar**. Todo
o trabalho do Studio vive só no seu disco.

**Correção, antes de qualquer outra coisa:**

```bash
# 1. crie o repositório do fork na sua conta (vazio, sem README)
# 2. depois:
git remote rename origin upstream
git remote set-url --push upstream DISABLED   # push acidental no upstream morre aqui
git remote add origin https://github.com/<SUA-CONTA>/hermes-omniroute-studio.git
git remote -v                                  # confira antes de empurrar
```

Manter `upstream` como fetch-only é o que permite continuar puxando correções da
Nous Research sem risco de empurrar para lá.

---

## 🔴 P0-2 — Varredura de segredos no histórico completo

O scan que roda hoje cobre o **estado atual**. O que importa aqui é o histórico:
depois de público, cada commit anterior é clonável por qualquer pessoa.

Eu já rodei uma varredura sobre os 21 commits desta branch: **todo hit é fixture
de redação** (`agent/redact.py`, `tests/agent/test_redact.py`,
`tests/gateway/test_slack*.py`, scripts de notarização e docs). Nenhuma
credencial real.

Mas isso cobre **esta branch**. Antes de publicar, rode sobre `--all`:

```bash
gitleaks detect --log-opts="--all" --report-path gitleaks.json
# ou
trufflehog git file://. --since-commit <primeiro-commit>
```

**Se aparecer qualquer coisa: a credencial está comprometida. Rotacione. Remover
do histórico não desfaz a exposição** — quem clonou, clonou.

Verificar em especial:
- `apps/desktop/scripts/.gitignore` ignora `share-codes.txt`. Confirme que
  nenhum `share-codes.txt` entrou em commit **anterior** à criação desse ignore.
- `tools/neutts_samples/`, fixtures, snapshots e logs versionados.
- `install-stamp.json`, relatórios de tarefa e gravações de sessão: nunca
  versionados — todos podem carregar caminho de usuário e conteúdo de workspace.

---

## 🟠 P1-3 — Canais de contato com marcador `<<PREENCHER>>`

Três arquivos têm um marcador deliberado no lugar de um endereço:

| Arquivo | O que falta |
|---|---|
| `SECURITY.md` | canal de segurança do Studio (bloco do topo) |
| `CODE_OF_CONDUCT.md` | canal de denúncia de conduta |
| `.github/ISSUE_TEMPLATE/config.yml` | links ainda apontam para o repositório upstream |

Não inventei endereços. Um canal de denúncia que não chega a ninguém é pior do
que nenhum canal: a pessoa acredita que reportou e espera. Preencha os três
antes de publicar.

Enquanto os marcadores existirem, relatos de segurança deste fork **não** devem
ir para `security@nousresearch.com` — a Nous Research não mantém este fork e não
tem como corrigi-lo.

---

## 🟠 P1-4 — Inventário de licenças das skills

`audit/HERMES_OPENSOURCE_READINESS.md` §1.3: o disco contém mais skills do que
qualquer documento declara (`humanizer`, `architecture-diagram`, `ascii-art`,
`ascii-video`, `baoyu-infographic`, `claude-design`, `comfyui`, `design-md` além
das listadas).

Falta uma tabela única e verificável:

| skill | origem (repo/URL) | licença | arquivo de licença no disco | redistribuição permitida | vai no instalador |
|---|---|---|---|---|---|

E um teste que **falha** se existir diretório de skill sem entrada em
`SOURCES.json` ou sem arquivo de licença — senão a próxima skill adicionada
reabre o buraco em silêncio.

Boa notícia já verificada: GSAP declara MIT e documenta que, depois da aquisição
pela Webflow, todos os plugins são livres inclusive para uso comercial, sem
chave nem membership. Era o risco jurídico mais provável de um bundle de skills
criativas, e não se materializou.

---

## 🟠 P1-5 — Build reproduzível

O instalador anterior saiu com `"dirty": true` no `install-stamp.json`: o SHA-256
confere com o esperado, então o artefato é o que diz ser — mas a **fonte** não é
reconstruível. É `9d80176` mais um delta não versionado que só existe na sua
máquina.

Para um projeto open source isso não fecha: a promessa central é que qualquer um
possa verificar o binário.

1. O script de release **falha** se o worktree estiver sujo.
2. `install-stamp.json` com `dirty: false` e `commit` batendo com o
   `git rev-parse HEAD` da tag.
3. SHA-256 do instalador publicado junto do release.
4. CI pública que constrói a partir da tag e publica o hash.
5. Assinatura. Sem certificado de code signing Windows, **documente honestamente
   o aviso do SmartScreen** em vez de fingir que ele não aparece.

---

## 🟡 P2-6 — CI pública que funciona em fork de terceiro

Os workflows precisam rodar em PR de gente de fora, **sem segredos**. Separe os
jobs que exigem credencial e faça-os pular graciosamente, com skip nomeado — a
mesma regra que já apliquei em `omniroute-security.test.ts`. Um job que falha
por falta de segredo em PR de terceiro faz o contribuidor achar que quebrou algo.

---

## Ordem sugerida

```
P0-1  remote          → sem isso não há onde publicar
P0-2  segredos        → irreversível depois de público
P1-3  canais          → 15 minutos, e sem eles as denúncias somem
P1-5  build           → precisa estar pronto na primeira tag
P1-4  licenças        → precisa estar pronto na primeira tag
P2-6  CI              → pode vir logo depois da primeira release
```
