# Auditoria de cadeia de suprimentos — R4

**Data:** 2026-08-22 · **HEAD:** `ae2008d` · **Ferramentas:** `npm audit`, `pip-audit`, `gitleaks 8.28.0`

> Toda linha aqui saiu de um comando executado, com a saída conferida contra o
> que o projeto realmente declara. A distinção que mais importa neste relatório é
> entre **o que o projeto pina** e **o que estava instalado no ambiente onde a
> varredura rodou** — confundir os dois transforma ruído de imagem-base em
> "38 vulnerabilidades no seu produto".

---

## 1. JavaScript — `npm audit`

```
vulnerabilidades: {info: 0, low: 0, moderate: 0, high: 0, critical: 0, total: 0}
```

**Zero.** Sobre 1.344 pacotes instalados a partir do `package-lock.json` da raiz
e dos workspaces (`apps/*`, `ui-tui`, `web`, `tests-js`).

---

## 2. Python — `pip-audit`

Saída bruta: **89 vulnerabilidades conhecidas em 12 pacotes**. Esse número
sozinho seria alarmante e estaria errado. A tabela abaixo separa o que é do
projeto do que é do ambiente:

| Pacote | Versão instalada | Vulns | O que o projeto declara | Veredito |
|---|---|---:|---|---|
| `python-multipart` | 0.0.26 | 4 | `>=0.0.9,<1` (base) e `==0.0.32` (extra `web`) | **ACHADO REAL — corrigido** |
| `urllib3` | 2.6.3 | 3 | `>=2.7.0,<3` | ambiente: o pino do projeto **já exige** a versão corrigida |
| `httplib2` | 0.20.4 | 2 | `==0.32.0` (extra `google`) | ambiente: o pino do projeto **já exige** a versão corrigida |
| `pypdf` | 3.17.4 | 37 | não declarado | ambiente (imagem-base) |
| `mistune` | 3.2.0 | 26 | não declarado | ambiente |
| `pip` | 24.0 | 7 | não declarado | ambiente |
| `pymdown-extensions` | 10.21.2 | 3 | não declarado | ambiente |
| `idna` · `soupsieve` | — | 2 cada | não declarado | ambiente |
| `pdfkit` · `pydantic-settings` · `wheel` | — | 1 cada | não declarado | ambiente |

**Um achado real em 89.** Os pinos de `urllib3` e `httplib2` inclusive já trazem
o motivo escrito em comentário no `pyproject.toml`, com o identificador do
GHSA — quem mantém este arquivo já vinha fazendo a coisa certa.

### 2.1 O achado — `python-multipart`

```
ARQUIVO  pyproject.toml:126 (antes: `python-multipart>=0.0.9,<1`)
CVEs     PYSEC-2026-3036, -3037, -3039, -3040
FIX      0.0.31 (o mais tardio dos quatro)
```

O piso `>=0.0.9` permitia que um resolvedor caísse em 0.0.26 e ficasse
vulnerável. O extra `web` já pinava `==0.0.32`, então a instalação completa
estava protegida — mas **a dependência base existe justamente para o endpoint de
upload do dashboard** (o comentário no arquivo diz isso), e é ela que é
alcançada em uma instalação sem o extra.

**Corrigido** para `>=0.0.32,<1`, alinhando o piso ao pino que o extra já usava.

### 2.2 O que ficou de fora, e por quê

`pypdf` aparece com 37 vulnerabilidades e é o maior número da lista, mas o
projeto **não o declara em lugar nenhum**. Ele é citado na documentação da skill
`skills/productivity/pdf` como algo que o usuário instala (`pip install pypdf`).
Isso não é uma vulnerabilidade do artefato publicado. Vale como melhoria de
higiene — a skill poderia sugerir um piso de versão — e está registrado como tal,
não como falha de segurança.

---

## 3. Segredos — `gitleaks` sobre o histórico completo

```
22 commits · 251,24 MB · exit 0 · no leaks found
```

Detalhe da triagem em `.gitleaks.toml`. Resumo: 1478 achados brutos → 0 após
exceções conferidas **uma a uma**, por regra + caminho. Nenhuma credencial real
no histórico. Provado com 4 canários plantados, incluindo um PAT do GitHub
dentro de `tests/` — que **é detectado**, porque a exceção de `tests/` cobre só a
heurística genérica de entropia.

Agora é portão de CI: `.github/workflows/secret-scan.yml`, com `fetch-depth: 0`
e sem nenhum segredo, para rodar em pull request de contribuidor externo.

---

## 4. Licenças

`audit/SKILL_LICENSE_INVENTORY.md`. 227 skills, todas com proveniência declarada;
27 vendorizadas de terceiros, todas MIT ou Apache-2.0, todas com o texto da
licença presente no disco. Portão: `tests/skills/test_skill_provenance.py`.

---

## 5. O que ainda não foi verificado

| Item | Estado |
|---|---|
| Assinatura dos artefatos Windows | sem certificado de code signing — documentar o aviso do SmartScreen honestamente, não fingir que não aparece |
| Notarização macOS | `BLOCKED_BY_EXTERNAL_DEPENDENCY` — exige conta Apple Developer |
| SBOM (CycloneDX/SPDX) | não gerado. Vale para uma release pública; não é bloqueador da primeira |
| `npm audit` do projeto Android (Capacitor) | pendente — `apps/mobile` tem árvore própria |
