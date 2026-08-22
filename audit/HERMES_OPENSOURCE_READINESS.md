# HERMES OMNIROUTE — PRONTIDÃO PARA OPEN SOURCE

Especificação de lançamento. Ancorada em `c573d47`.

---

## 1. SITUAÇÃO DE LICENÇA

### 1.1 Base
O projeto é obra derivada de **NousResearch/hermes-agent** sob **MIT**. `LICENSE` na raiz preserva o copyright original, e `NOTICE-OMNIROUTE-STUDIO.md` declara a derivação, a identidade separada do Studio (`com.dz23.hermesomniroute`, executável `HermesOmniRoute`, protocolo `hermes-omniroute`) e que OmniRoute e Caveman são projetos separados com licenças próprias.

**MIT permite redistribuição, modificação e uso comercial, exigindo preservação do aviso de copyright.** Está cumprido. Nada bloqueia o open source pela base.

### 1.2 Skills de terceiros — verificado, e está correto
```text
skills/creative/gsap/LICENSE
skills/creative/img2threejs/LICENSE
skills/creative/motion-design/LICENSE
skills/creative/humanizer/LICENSE
skills/creative/design-toolkit/LICENSE.daymade
skills/creative/design-toolkit/LICENSE.impeccable
skills/creative/design-toolkit/LICENSE.nextlevelbuilder
skills/creative/design-toolkit/frontend-design/LICENSE.txt
skills/creative/SOURCES.json · skills/creative/design-toolkit/SOURCES.json
```
GSAP declara `license: MIT` e documenta que, após a aquisição pela Webflow, **todos os plugins são livres inclusive para uso comercial**, sem chave nem membership. Isto era o risco jurídico mais provável de um bundle de skills criativas, e ele **não se materializou**.

### 1.3 O que ainda falta — P1
**Inventário divergente.** O disco contém mais skills do que qualquer documento declara. Além das listadas nos handoffs, existem: `humanizer`, `architecture-diagram`, `ascii-art`, `ascii-video`, `baoyu-infographic`, `claude-design`, `comfyui`, `design-md`.

Antes do lançamento, produzir uma tabela única e verificável:

| skill | origem (repo/URL) | licença | arquivo de licença no disco | redistribuição permitida | presente no instalador |
|---|---|---|---|---|---|

E um teste que **falha** se existir diretório de skill sem entrada em `SOURCES.json` ou sem arquivo de licença. Isso impede regressão silenciosa quando alguém adicionar a próxima skill.

---

## 2. HIGIENE DE SEGREDOS — P0 antes de tornar público

Tornar público é **irreversível**: o histórico inteiro fica exposto e clonável. Antes de qualquer publicação:

1. **Varredura do histórico completo**, não do worktree. `gitleaks detect --log-opts="--all"` ou `trufflehog git file://. --since-commit <primeiro>`. O secret scan que roda hoje cobre o estado atual, não os commits anteriores.
2. O handoff registra que *"qualquer segredo exposto anteriormente deve ser tratado como comprometido"*. **Se a varredura encontrar algo, a credencial precisa ser rotacionada — remover do histórico não desfaz a exposição.**
3. Verificar especificamente: `apps/desktop/scripts/.gitignore` ignora `share-codes.txt` — confirmar que nenhum `share-codes.txt` entrou em commit anterior à criação desse ignore.
4. Verificar `tools/neutts_samples/`, fixtures de teste, snapshots e logs versionados.
5. Confirmar que `install-stamp.json`, relatórios de tarefa e gravações de sessão (F2) **nunca** são versionados — todos podem conter caminho de usuário ou conteúdo de workspace.

**Não publique antes desta varredura passar com saída anexada.**

---

## 3. ARQUIVOS DE GOVERNANÇA

Existem hoje: `LICENSE`, `README.md` (+ es/zh-CN/ur-pk), `CONTRIBUTING.md` (+ es), `SECURITY.md` (+ es), `AGENTS.md`, `NOTICE-OMNIROUTE-STUDIO.md`, `website/` com Docusaurus.

**Base sólida.** Falta adaptar ao fork:

| Arquivo | Estado | Ação |
|---|---|---|
| `README.md` | banner do fork já existe | reescrever o topo: o que é, para quem, screenshot, instalação em 3 passos, link para docs |
| `CONTRIBUTING.md` | herdado do upstream | adaptar: gates reais (`npm run --prefix apps/desktop typecheck/lint/test`), política de commit isolado, regra de nenhum `process.platform` em corpo de teste |
| `SECURITY.md` | herdado | **canal de report próprio** — o do upstream não deve receber report deste fork; adicionar escopo, prazo de resposta e política de divulgação |
| `CODE_OF_CONDUCT.md` | **ausente** | criar (Contributor Covenant) |
| `NOTICE` / atribuições | parcial | consolidar a tabela de §1.3 |
| `CHANGELOG.md` | **ausente** | criar, começando na primeira release pública |
| `.github/ISSUE_TEMPLATE/` | verificar | bug / feature / security-não-aqui |
| `.github/PULL_REQUEST_TEMPLATE.md` | verificar | checklist de gates |

---

## 4. BUILD REPRODUZÍVEL — P1

O instalador anterior saiu com `"dirty": true` no `install-stamp.json` — ou seja, **não era reconstruível por ninguém**. Para um projeto open source isso é inaceitável: a promessa central é que qualquer um pode verificar o binário.

Requisitos:
1. Script de release **falha** se o worktree estiver sujo.
2. `install-stamp.json` com `dirty: false` e `commit` batendo com o `git rev-parse HEAD` da tag.
3. SHA-256 do instalador publicado junto com o release.
4. CI pública que constrói a partir da tag e publica o hash — para qualquer pessoa comparar.
5. Assinatura de release. Sem certificado de code signing Windows, documente honestamente o aviso do SmartScreen em vez de fingir que não existe.

---

## 5. CI PÚBLICA

O F4 tornou `windows-primary` a lane obrigatória. Para o open source:
- workflows precisam rodar em fork e em PR de terceiro **sem segredos** — separe jobs que exigem credencial e faça-os pular graciosamente, com skip nomeado;
- publicar o status: badge no README;
- o lint `test:platform-guards` e o fuzzer do guardrail entram no gate público — são o que dá confiança de que a camada de segurança não regrediu;
- **nunca** exponha em log público: caminhos do usuário, tokens, nomes de host internos.

---

## 6. O QUE NÃO PODE IR PARA O PÚBLICO

- Nenhuma credencial, cookie, token ou chave — em código, histórico, fixture, screenshot ou log.
- Nenhum caminho absoluto de usuário real em teste, snapshot ou documentação (`C:\Users\zodyp\...` deve virar placeholder).
- Nenhum relatório de tarefa, gravação de sessão ou `install-stamp` de máquina real.
- Nenhum artefato de `audit/_raw/` — tarballs e diffs de trabalho. **Confirme que `audit/_raw/` está no `.gitignore`.**
- Nenhum backup (`hermes-r2-backup-*`) dentro do repositório.

---

## 7. POSICIONAMENTO — o que diferencia este fork

Para um lançamento honesto, o README precisa dizer o que o projeto **é** e o que ele **não é**. O diferencial real, com base nas três auditorias:

**O que o Hermes OmniRoute Studio tem que os concorrentes não têm:**
- **Proveniência de contexto (F1)** — escala aprovação quando uma operação privilegiada é proposta logo após entrada de conteúdo externo. Determinístico, não depende do modelo.
- **Guardrail determinístico auditado** — 18/18 comandos destrutivos bloqueados, 0/5 falsos positivos, com fuzzer de 665 casos.
- **Gate de verificação que exige exit code real**, não heurística de texto.
- **Teto de gasto que o próprio agente não desliga (F6).**
- **Replay de sessão (F2)** — transforma uso real em teste de regressão.
- **Roteamento multi-modelo local** via OmniRoute, sem depender da nuvem de um fornecedor.

**O que ele não é** — e dizer isso protege o projeto:
- não é um serviço hospedado;
- não contorna cobrança nem termos de nenhum provedor de modelo (login de assinatura Claude/ChatGPT **não** é suportado, por decisão explícita);
- não é auditado por terceiro independente credenciado;
- suporte a macOS e Linux existe mas Windows é o alvo primário e o único com CI obrigatória hoje.

---

## 8. SEQUÊNCIA DE LANÇAMENTO

```
1. Varredura de segredos no histórico COMPLETO           ← bloqueante, P0
2. Tabela de skills × origem × licença + teste que falha  ← bloqueante, P1
3. .gitignore: audit/_raw/, backups, artefatos            ← bloqueante
4. Governança: CoC, SECURITY próprio, CONTRIBUTING, templates
5. README de produto + screenshots + instalação em 3 passos
6. Build reproduzível com dirty:false + SHA-256 publicado
7. CI pública verde, incluindo guardrail e platform-guards
8. Tag + release + CHANGELOG
9. Só então tornar o repositório público
```

**Ordem importa.** Tornar público antes do item 1 é irreversível.

---

## 9. PRIMEIRA TAREFA

Antes de escrever qualquer arquivo de governança, rodar e anexar:

```powershell
# histórico completo, não só o worktree
gitleaks detect --source . --log-opts="--all" --report-path secrets-history.json

# o que está versionado que não deveria
git ls-files | Select-String -Pattern "audit/_raw|\.bundle$|task-reports|session-recordings"

# caminhos de usuário real versionados
git grep -n "C:\\\\Users\\\\zodyp" -- . | Select-Object -First 40
```

Esses três comandos definem se o projeto está a dias ou a semanas do lançamento público.
