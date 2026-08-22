# Changelog

Todas as mudanças relevantes deste projeto ficam registradas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o
versionamento segue [SemVer](https://semver.org/lang/pt-BR/).

Este arquivo começa no fork. O histórico anterior ao fork é o do
[Hermes Agent](https://github.com/NousResearch/hermes-agent) upstream.

---

## [Não lançado]

### Segurança

- **Executores remotos de pacote passaram a ser detectados.** `npx`, `bunx`,
  `uvx`, `pnpm dlx`, `yarn dlx`, `npm exec` e `pipx run` baixam um pacote de um
  registro público e o executam em um passo. Nenhum disparava aprovação,
  enquanto `curl | sh` — a mesma operação — já era achado hardline. As formas
  garantidamente locais (`npx --no-install`, `npx --no`) continuam silenciosas.
- **`pip install --target . <pacote>` deixou de escapar da regra de
  supply-chain.** O grupo de opções do regex consumia `--target` mas não o valor
  da opção, e o pacote nunca era visto. Substituído por caminhamento de tokens.
- **A regra de fork bomb passou a casar a forma, não uma grafia.**
  `: (){ :|:& };:` (um espaço) e `bomb(){ bomb|bomb& };bomb` (qualquer outro
  nome) passavam pelo piso hardline.
- **O fallback do guardrail dz23 deixou de ser permissivo.** Quando
  `tools.approval` não importa, o plugin cai em um caminho degradado que se
  descrevia como "conservador" e não era: `r\m -rf`, `r''m -rf`, `$(rm -rf …)` e
  a forma com crase passavam. Corrigido e coberto por 14 testes que forçam o
  caminho degradado explicitamente.

### Corrigido

- **Fim de linha normalizado em toda a árvore.** `* text=auto eol=lf` virou
  regra padrão do `.gitattributes`. Sem ela, todo arquivo sem extensão ficava
  com atributo `unspecified` e acumulava CRLF em checkout Windows. Impacto real:
  `./hermes`, `docker/s6-rc.d/*/run`, `docker/cont-init.d/*` e
  `scripts/hermes-gateway` são executados por loader POSIX e estavam com CRLF —
  o shebang seria lido como `/usr/bin/env python3\r` e o container não subiria.
- **`windows-hermes-path.test.ts` deixou de depender do host.** O teste
  comparava com `path.join` (sabor do host) o que a função constrói com
  `path.win32.join`; falhava em POSIX por defeito de projeto do teste, não do
  código.
- **`omniroute-security.test.ts` deixou de falhar sem instalação local.** O
  teste de integração virou `test.skipIf` nomeado, então a ausência do
  `~/.omniroute/storage.sqlite` aparece como skip com motivo em vez de erro.

### Adicionado

- `CODE_OF_CONDUCT.md`, `CHANGELOG.md` e o bloco de roteamento de segurança do
  fork em `SECURITY.md`.
- `tests/tools/test_package_fetch_guard.py` — 86 testes.
- `tests/plugins/test_dz23_guardrail_fallback.py` — 14 testes.
- `BUILD-E-INSTALAR.bat` / `build-and-install-preview.ps1` — build e instalação
  do preview sem tocar no worktree, com verificação de identidade, backup de
  perfil e conferência de paridade pós-instalação.

---

## Como escrever uma entrada aqui

Uma entrada útil diz **o que mudou para quem usa**, não o que mudou no arquivo.
"Corrige regex em approval.py" não ajuda ninguém; "`pip install --target .`
deixou de escapar da regra de supply-chain" ajuda. Quando a mudança é de
segurança, diga qual era o comportamento antes — quem lê precisa saber se estava
exposto.
