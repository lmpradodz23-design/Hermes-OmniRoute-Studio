# RAPTOR — Auditoria de Licenças

Alvo: `github.com/gadievron/raptor` @ `26c52be` · versão 3.0.0.
Contexto: integração ao Hermes OmniRoute Studio, um produto distribuído. A
pergunta que esta auditoria responde não é "o RAPTOR é MIT?" — é "o que pode ser
distribuído com o Hermes, e o que precisa ficar atrás de um provider opcional?".

## Resumo executivo

| componente | licença | pode distribuir? | posição na integração |
|---|---|---|---|
| RAPTOR (código próprio) | MIT | Sim | adapter isolado, não copiado no core |
| Semgrep (OSS) | LGPL 2.1 | Sim (invocado, não linkado) | scanner **obrigatório**, invocado como binário externo |
| **CodeQL** | **GitHub CodeQL Terms** | **NÃO para uso comercial** | provider **opcional**, desligado por padrão (`--no-codeql`) |
| Coccinelle (spatch) | GPLv2 | invocado como binário externo | opcional |
| radare2 | LGPLv3 | invocado como binário externo | opcional |
| GDB / rr | GPLv3 | invocado como binário externo | opcional (binary analysis) |
| AFL++ | Apache 2.0 | invocado como binário externo | opcional (fuzz) |
| Frida | wxWindows/… | invocado como binário externo | opcional (alpha) |
| SecOpsAgentKit (submódulo) | **NÃO AUDITADO** | — | vazio no checkout; auditar se inicializado |

## Constatação central — CodeQL

O próprio README do RAPTOR declara, em `README.md:35` e `:562`:

> "CodeQL has its own licence and does not permit commercial use."

Isto é uma **restrição de licença de terceiro**, não do RAPTOR. Consequência
para o Hermes, que é distribuído:

- **CodeQL NÃO pode ser dependência obrigatória** nem redistribuído no
  instalador.
- Na arquitetura da integração, CodeQL é um `OptionalCodeQLProvider` — o
  `RaptorAdapter` passa `--no-codeql` por padrão (`security_research/adapter.py`
  `scan_argv`), e o Security Research funciona inteiro sem ele, com o Semgrep
  como motor default.
- No código do RAPTOR isso é isolável: `raptor_agentic.py:2590`
  `run_codeql = (args.codeql or args.codeql_only) and not args.no_codeql` — o
  agentic não roda CodeQL a menos que explicitamente pedido.

Decisão registrada: **`BLOCKED_BY_LICENSE_CONSTRAINT` para qualquer caminho que
torne o CodeQL obrigatório ou o redistribua.** O provider existe, mas
desabilitado por padrão e nunca empacotado.

## Semgrep

LGPL 2.1. O Hermes o **invoca como processo externo** (não faz link estático
nem incorpora código), o que não dispara as obrigações de copyleft de linkagem.
Não é redistribuído no instalador do Hermes: é detectado por preflight
(`shutil.which`) e o usuário o instala/configura. Estado na UI quando ausente:
`DEPENDENCY_REQUIRED` para as operações de scan estático; o resto do Security
Research (threat model, histórico, relatórios) continua utilizável.

## Sem código não-MIT embutido

A auditoria da árvore (Wave 0) não encontrou diretório `vendor/`/`third_party/`
nem headers de licença de terceiros no código Python do RAPTOR. As ocorrências
de "GPL"/"Apache"/"BSD" em `.py` são **dados** do classificador de licença do
próprio RAPTOR (`core/license/`, `packages/sca/license.py`), não código
importado. O único `LICENSE` aninhado (`packages/cve_env/LICENSE`) é MIT do
mesmo autor.

## Submódulo não auditado

`.gitmodules` declara `SecOpsAgentKit`
(`github.com/AgentSecOps/SecOpsAgentKit`) em `.claude/skills/`. No checkout está
**vazio** (não inicializado). A integração **não** o inicializa. Se um dia for
necessário, exige auditoria de licença própria antes de qualquer uso —
registrado como pré-condição.

## Modelo de distribuição adotado

O Hermes **não empacota** nenhum scanner de terceiro. O RAPTOR entra como
checkout isolado/vendored (decisão em `RAPTOR_INTEGRATION_ARCHITECTURE.md`), e
os scanners externos são todos detectados-e-opcionais. Isso mantém o instalador
enxuto e evita redistribuir componentes com licença incompatível — sobretudo o
CodeQL.

## Blockers de licença

```
BLOCKER-ID=RAPTOR-LIC-1
TYPE=BLOCKED_BY_LICENSE_CONSTRAINT
COMPONENT=CodeQL
REASON=GitHub CodeQL Terms proíbem uso comercial; Hermes é distribuído
WHAT_WAS_VERIFIED=README:35/562 declaram a restrição; --no-codeql isola no código
WHAT_COULD_NOT_BE_VERIFIED=nada — a restrição é explícita e documentada
EXACT_REQUIREMENT_TO_UNBLOCK=licença comercial do CodeQL, OU manter opcional/desligado (adotado)
```

```
BLOCKER-ID=RAPTOR-LIC-2
TYPE=BLOCKED_BY_EXTERNAL_DEPENDENCY
COMPONENT=SecOpsAgentKit (submódulo)
REASON=não presente no checkout; licença/conteúdo desconhecidos
WHAT_WAS_VERIFIED=.gitmodules aponta para o repo; diretório vazio
EXACT_REQUIREMENT_TO_UNBLOCK=auditoria de licença do submódulo se/quando for usado
```
