# RAPTOR Integration Report

## Executive summary

O RAPTOR (`gadievron/raptor` @ 26c52be, MIT, v3.0.0) foi auditado e a fundação da
sua integração ao Hermes OmniRoute Studio foi implementada com baixo acoplamento
e testada contra o RAPTOR real. O que está pronto: a camada Python de domínio de
segurança (adapter, findings, SARIF, fronteira de projeto, permissões, runtime)
— 55 testes, incluindo uma execução viva do RAPTOR e a normalização do SARIF que
ele realmente produziu. O que depende do dispositivo Windows do usuário (UI
Electron, packaging NSIS, sandbox de execução não confiável, E2E do app
instalado) está registrado como `BLOCKED_BY_PLATFORM_SECURITY`/device-required —
não como concluído.

## Architecture

`Hermes → OmniRoute → SecurityEngine → RaptorAdapter → RAPTOR (modos planos)`.
Baixo acoplamento: um único adapter conhece o RAPTOR; nenhum código do RAPTOR no
core. Detalhes em `docs/RAPTOR_INTEGRATION_ARCHITECTURE.md`.

## Upstream RAPTOR version

3.0.0 · commit 26c52bea4a59edd2a6eda6bb6b2a6cbff9a30b0b · MIT.

## Licensing

MIT no código próprio. **CodeQL sob GitHub Terms (proíbe uso comercial)** →
provider opcional, `--no-codeql` por padrão, nunca redistribuído. Semgrep
(LGPL 2.1) invocado como binário externo, não empacotado. Detalhes em
`docs/RAPTOR_LICENSE_AUDIT.md`.

## Capabilities integradas (modos planos)

`describe` (preflight), `scan` (Semgrep→SARIF), `sca`, `analyze`. Todos por argv,
sem shell, dentro da fronteira do projeto. Modos de execução não confiável
gated por sandbox. Workflows agênticos (dependem de Claude Code no upstream)
não integrados por design neste estágio.

## Security model

Fronteira de projeto (path traversal), argv-only (command injection), SARIF com
validação de tamanho/estrutura, tetos de saída, matriz de capacidades com mínimo
privilégio, e máquina de estados que barra "verde artificial". Todo output de
scanner/LLM/SARIF é UNTRUSTED. Enforcement no ponto de execução, não no prompt.

## Sandbox

RAPTOR: Linux (namespaces/Landlock/seccomp) + macOS (Seatbelt). Zero Windows.
`SandboxProvider` (`runtime.detect_sandbox`) reporta o backend real e bloqueia
execução não confiável sem isolamento. No Windows o caminho suportado é
WSL2/container.

## MCP / Agent / Memory / Goal / Product Studio integration

Pendente (Wave 6+): expor `security.describe/scan/findings/validate/report` como
ferramentas MCP no `tui_gateway`, reusando o adapter; conectar findings à
memória e Goal. As 107 ferramentas MCP existentes não foram tocadas.

## Security Studio UX

Device-required (Wave 8). A arquitetura e o modelo de dados estão prontos; a UI
Electron será escrita e testada com vitest, mas o E2E exige o app instalado.

## Findings (da própria integração)

Nenhum finding interno reproduzível em aberto na fundação implementada. As
defesas têm testes adversariais que reprovam quando a defesa é desfeita.

## Tests

`security_research/`: 55/55 passed. Inclui execução real do RAPTOR `describe` e
normalização do SARIF real. Regressão do Hermes: o fix loop das três auditorias
(commit anterior) segue verde; esta fundação é aditiva e não toca o core.

## Performance

`raptor.py scan` de 1 arquivo/6 linhas: ~90s, SARIF de 3,2 MB (medido).
`describe`: <2s. Demais métricas: NOT_MEASURED (exigem o app instalado).

## Windows / packaging

RAPTOR (117 MB, sandbox Linux) NÃO entra no instalador NSIS. Configurado à parte
no ambiente Linux (WSL2/container). Chassis Bash do RAPTOR (`bin/*`) não usado —
invocação direta de `raptor.py` por argv.

## External blockers

CodeQL (licença), sandbox Linux no Windows (plataforma), Security Studio
UI/packaging/E2E (device), SecOpsAgentKit não auditado (submódulo vazio). Todos
registrados no checkpoint.

## Known limitations

Nenhum workflow agêntico do RAPTOR foi integrado (dependem de Claude Code).
Modos de execução não confiável não rodam no Windows nativo. A UI ainda não
existe. Estas são limitações de escopo/plataforma declaradas, não bugs.

## Git state

Ver saída de `git status` no fim da entrega. DO_NOT_PUSH / DO_NOT_RELEASE.
