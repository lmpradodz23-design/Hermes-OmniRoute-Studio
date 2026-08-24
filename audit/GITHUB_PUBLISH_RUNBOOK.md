# Runbook — Publicar Hermes OmniRoute Studio como repo open source

Para você rodar **no PC (PowerShell)**, dentro de
`C:\Users\you\Documents\Codex\Hermes-OmniRoute`. Eu não executo isto (não
manuseio suas credenciais GitHub e o WSL não tem rede). Requer `git` e `gh`
autenticados (`gh auth status`).

Estado apurado por mim:
- `origin` = `https://github.com/NousResearch/hermes-agent.git` (**UPSTREAM** — nunca dar push aqui).
- branch atual = `feature/hermes-omniroute-studio` @ `ae2008d…`.
- minhas entregas (RAPTOR/OpenWA/U1/Model-Routing/Context/Agents/Goals/Memory/
  updater P0 + docs) estão **no working tree como UNTRACKED** — precisam commit.
- LICENSE = MIT (Nous Research) — preservado. SECRET_SCAN de conteúdo = limpo.
  `.gitignore` endurecido (nesta entrega).

## NÃO FAZER
- NÃO `git push origin` (origin é o upstream). Use o remote NOVO `oss`.
- NÃO `git add -A` cego sem rodar o gitleaks antes.
- NÃO commitar `state.db`, `.env`, `auth.json`, sessões WhatsApp, venv, node_modules
  (o `.gitignore` já cobre; confirme com o passo 3).
- NÃO criar release/tag `vX` agora. NÃO marcar como stable.

## 1. Sanidade + backup do estado atual
```powershell
git status
git log --oneline -3
git branch --show-current
git remote -v
git bundle create ..\hermes-omniroute-backup.bundle --all   # backup do histórico
```

## 2. Commitar minhas entregas (untracked) na branch atual
```powershell
git add apps/desktop/ whatsapp_provider/ security_research/ tests/ audit/ docs/ .gitignore THIRD_PARTY_NOTICES.md
git status                      # revise o que entrou — NENHUM .env/.db/auth/session
git commit -m "feat: OmniRoute Studio (U1, RAPTOR/OpenWA adapters, MCP, updater P0 fix) + docs OSS"
```
(Ajuste os paths se quiser granularidade. Revise o diff antes do commit.)

## 3. GATE de segredo OBRIGATÓRIO (o repo já tem .gitleaks.toml)
```powershell
gh extension install gitleaks/gitleaks 2>$null; # ou baixe o binário gitleaks
gitleaks detect --source . --config .gitleaks.toml --redact --no-banner
# esperado: "no leaks found". Se achar QUALQUER coisa real: PARE, remova, refaça.
```
Também rode um scan do histórico antes de publicar:
```powershell
gitleaks detect --source . --config .gitleaks.toml --redact --log-opts="--all"
```

## 4. Criar o repositório PÚBLICO novo (conta autorizada)
```powershell
gh repo create Hermes-OmniRoute-Studio --public `
  --description "Open-source autonomous engineering & agent desktop, built on Hermes + OmniRoute (development / pre-release)" `
  --disable-wiki
```
(Se a org exigir lowercase, use `hermes-omniroute-studio`.)

## 5. Adicionar o remote NOVO (preservando o upstream em `origin`)
```powershell
gh repo view Hermes-OmniRoute-Studio --json url -q .url    # confirme a URL
git remote add oss https://github.com/<SUA_CONTA>/Hermes-OmniRoute-Studio.git
git remote -v            # origin=NousResearch (upstream), oss=seu repo novo
```

## 6. Publicar em `develop` (não em main — ainda há validação pendente)
```powershell
git branch develop            # a partir da branch atual
git push -u oss develop
# opcional: também publicar a branch de trabalho tal como está
git push oss feature/hermes-omniroute-studio
```
Defina `develop` como default branch no GitHub (Settings → Branches) enquanto
não houver o gate final. NÃO promova para `main` só para "parecer pronto".

## 7. Verificar no GitHub
- README renderiza e diz "Development / Pre-release".
- LICENSE (MIT, Nous Research) presente; `THIRD_PARTY_NOTICES.md` presente.
- Nenhum `.env`/`.db`/`auth.json`/sessão/venv/node_modules na árvore.
- Actions (se `.github/workflows` tiver CI) rodando; sem secrets no workflow.
- Branch default = `develop`.

## 8. Proteção (quando quiser, sem travar o dev)
- Settings → Code security: habilitar **secret scanning** + **Dependabot alerts**.
- Branch protection em `main` (quando existir): PR + CI obrigatório. Deixe
  `develop` livre para o desenvolvimento contínuo.

## Depois do push — me informe para eu preencher o handoff (§29)
`REPOSITORY_URL`, `DEFAULT_BRANCH`, `HEAD_SHA` — e eu retomo o desenvolvimento
fazendo commits incrementais em `develop` (após targeted tests + secret scan +
self-review), sem criar release.
