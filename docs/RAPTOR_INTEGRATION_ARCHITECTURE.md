# RAPTOR — Arquitetura de Integração

Alvo: `github.com/gadievron/raptor` @ `26c52be` (MIT, 3.0.0). Este documento
registra as decisões de arquitetura da integração ao Hermes OmniRoute Studio,
todas baseadas na auditoria de código do Wave 0 (não no README).

## A decisão de acoplamento

```
Hermes Agent → OmniRoute → SecurityEngine → RaptorAdapter → RAPTOR (modos planos)
```

O Hermes mantém missão, autorização, observabilidade e UX. O RAPTOR executa
capacidade especializada, **atrás de um único adapter** (`security_research/
adapter.py`). Nenhum código do RAPTOR é copiado para o core do Hermes. Trocar,
atualizar, desabilitar ou isolar o RAPTOR é mexer só no adapter.

## Três verdades da auditoria que moldam tudo

**1. O sandbox do RAPTOR é Linux + macOS. Zero Windows.**
`core/sandbox/` usa user/net/pid/mount namespaces + Landlock + seccomp (Linux) e
Seatbelt (macOS). Não há ramo `win32`. O Hermes roda no Windows. Consequência
inegociável:

> Modos que executam conteúdo não confiável (`fuzz`, `exploit`, `crash-analysis`,
> `cve-env`, `frida`, `binary`) **não têm contenção no Windows nativo**. Na
> integração, esses modos retornam `BLOCKED_BY_PLATFORM_SECURITY` a menos que
> haja um backend de sandbox real (WSL2 ou container Linux).

Isto é enforçado em código: `runtime.detect_sandbox()` reporta o backend real, e
`adapter.RaptorAdapter._guard_mode` recusa os modos de execução não confiável
sem `can_isolate_untrusted_exec`. Nenhuma UI finge que o sandbox Linux protege o
Windows.

**2. A orquestração agêntica do RAPTOR é Claude-Code-only; os modos planos não.**
`README.md:360`: "The orchestration layer is always Claude Code." Os workflows
`/audit`, `/understand`, `/validate`, `/exploit`, `/patch`, `/crash-analysis`,
`/oss-forensics` rodam dentro de uma sessão Claude Code (skills/agents em
`.claude/`). MAS os **modos planos** — `describe`, `scan`, `sca`, `analyze`,
`codeql`, `doctor` — rodam por `python3 raptor.py <mode>` **sem** Claude Code e
emitem JSON/SARIF (`README.md:479`).

> Decisão: a integração é construída sobre os **modos planos**. São os que
> rodam de forma controlada, multi-modelo, e cujo output é normalizável. Os
> workflows agênticos ficam como extensão futura, roteável via OmniRoute quando
> o Hermes puder hospedar a orquestração — não pela dependência do Claude Code.

Isto também satisfaz o requisito multi-model (§7): a camada de modelo do RAPTOR
(`core/llm/`) já é genuinamente multi-provider (anthropic/openai/gemini/mistral/
bedrock/ollama), então a seleção de modelo continua no OmniRoute.

**3. O chassis do RAPTOR (`bin/*`) é Bash/Unix.** `bin/raptor` faz `exec claude`.
Não roda em Windows nativo. A integração **não usa `bin/*`** — invoca `raptor.py`
diretamente por argv (`python + raptor.py + <mode> + argv[]`), o que é
multiplataforma no que depende do adapter.

## Estratégia de aquisição do RAPTOR (§68/§69)

Avaliadas: submódulo, subtree, package, checkout externo, managed runtime.

Decisão: **checkout externo isolado gerenciado pelo Hermes** (não submódulo
automático, não subtree no repo). Justificativa:

- **Atualização**: um checkout com pin de commit (`RAPTOR_COMMIT`) atualiza sem
  reescrever o histórico do Hermes; a estratégia de update é bump explícito do
  pin + reteste do adapter.
- **Windows/installer**: o RAPTOR (117 MB, sandbox Linux) **não** entra no
  instalador NSIS do Hermes. É configurado/baixado à parte, no ambiente Linux
  (WSL2/container) onde ele realmente funciona.
- **Licença**: nenhum código de terceiro entra na árvore do Hermes; o CodeQL
  nunca é redistribuído.
- **Segurança**: o RAPTOR fica num diretório isolado, e o adapter é o único
  ponto de contato. O `raptor_root` é configuração, não código embutido.
- **Offline**: o pin permite operação reproduzível sem `main` móvel.

`RAPTOR_VERSION` / `RAPTOR_COMMIT` / `ADAPTER_VERSION` são registrados no
checkpoint e no relatório.

## Trust boundaries

```
Electron Renderer
      │  (IPC validado — nunca primitive perigosa exposta direto)
      ▼
Hermes Gateway (Python)  ──  SecurityEngine
      │
      ▼
RaptorAdapter  (argv-only, shell=False, tetos de saída, timeout, PID, cancel)
      │
      ▼
RAPTOR (modo plano)  →  Semgrep / SARIF   [UNTRUSTED OUTPUT]
      │
      ▼
SARIF parser (tamanho/estrutura validados) → Finding normalizado (CANDIDATE)
      │
      ▼
Fronteira de projeto (resolve todo caminho DENTRO do alvo autorizado)
```

Tudo à direita de "UNTRUSTED OUTPUT" — SARIF, saída de scanner, saída de LLM,
conteúdo do repositório analisado — é **dado, nunca instrução**. A defesa não é
o prompt; é o enforcement no ponto de execução: `run_argv` nunca usa shell, o
parser de SARIF valida tamanho e estrutura, e todo caminho passa por
`AuthorizedTarget.resolve`.

## Componentes implementados (Wave 0-5)

| módulo | papel |
|---|---|
| `security_research/boundary.py` | fronteira de projeto — defesa de path traversal, num só lugar |
| `security_research/findings.py` | Finding normalizado + máquina de estados (CANDIDATE→…→FIXED) + dedup |
| `security_research/sarif.py` | ingestão de SARIF hostil (tamanho, estrutura, uri dentro da fronteira) |
| `security_research/permissions.py` | matriz de capacidades, mínimo privilégio |
| `security_research/runtime.py` | execução argv-only + `SandboxProvider` (a verdade sobre a plataforma) |
| `security_research/adapter.py` | o único ponto que conhece o RAPTOR; modos planos + gate de plataforma |

## O que exige o dispositivo Windows (não implementável/testável no cloud)

Registrado honestamente como pendente de plataforma, não como concluído:

- **Security Studio UI** (Electron/React) — pode ser escrita e testada com
  vitest, mas o E2E do app instalado exige a máquina.
- **Packaging NSIS / installed-app smoke** — exige build no Windows.
- **Sandbox real de execução não confiável** — exige WSL2/container Linux 3.12+
  no ambiente do usuário; no cloud atual (Linux 3.11) o próprio sandbox do
  RAPTOR não sobe.
- **Matriz das 107 ferramentas MCP + novas `security.*`** — a reexecução da
  matriz e o registro das ferramentas MCP de segurança acontecem no gateway do
  app.

Estes são `BLOCKED_BY_PLATFORM_SECURITY` / device-required, entregues como
prompts prontos para o executor no ambiente do usuário quando aplicável.
