# RAPTOR_INTEGRATION_CHECKPOINT

```
MISSION_STATUS=IN_PROGRESS — fundação (Wave 0-5) implementada e testada; UI/Windows/E2E dependem do dispositivo
CURRENT_WAVE=6 (agents/OmniRoute/MCP) próximo; Waves 8/12/14 são device-required
COMPLETED_WAVES=0 (baseline+arquitetura), 1 (adapter/runtime), 2 (domínio/modelo), 3 (scanner Semgrep), 5 (findings/validação) — parcial: 4 (attack surface/threat model) pendente
OPEN_INTERNAL_FIXABLE=0
EXTERNAL_BLOCKERS=3 (CodeQL licença; sandbox Linux no Windows; SecOpsAgentKit não auditado)
LAST_FULL_TEST=security_research 55/55 passed; RAPTOR describe real PASSED
FINAL_REPORT=audit/RAPTOR_INTEGRATION_REPORT.md
NEXT_ACTION=Wave 6 — expor security.describe/scan/findings como ferramentas MCP no tui_gateway, reusando o adapter; depois Wave 8 (Security Studio UI) que é device-required
```

## RAPTOR

```
RAPTOR_VERSION=3.0.0
RAPTOR_COMMIT=26c52bea4a59edd2a6eda6bb6b2a6cbff9a30b0b
RAPTOR_LICENSE=MIT (com CodeQL sob restrição de uso comercial — provider opcional)
ADAPTER_VERSION=0.1.0
```

## O que foi feito neste turno (evidência)

- **Wave 0 — auditoria + docs.** RAPTOR clonado e auditado por subagente
  independente (arquitetura, acoplamento Claude Code, sandbox Linux/macOS,
  27 capacidades por status, licenças). Docs: `RAPTOR_LICENSE_AUDIT.md`,
  `RAPTOR_INTEGRATION_ARCHITECTURE.md`, `SECURITY_RESEARCH.md`.
- **Wave 1-5 — fundação Python, testada.** `security_research/`:
  - `boundary.py` — defesa de path traversal (11 testes adversariais)
  - `findings.py` — Finding + máquina de estados + dedup (12 testes)
  - `sarif.py` — ingestão de SARIF hostil + normalização do SARIF **real** do
    RAPTOR (10 testes)
  - `permissions.py` — matriz de capacidades, mínimo privilégio (5 testes)
  - `runtime.py` — execução argv-only + SandboxProvider honesto sobre Windows
  - `adapter.py` — o único ponto que conhece o RAPTOR; modos planos + gate de
    plataforma (17 testes, incl. execução REAL do `describe`)
  - Total: **55/55 passed**. Canário: enfraquecer a fronteira derruba 6 testes.
- **Prova de integração viva.** `test_real_raptor_describe_runs` invoca o RAPTOR
  real (`/tmp/raptor`) pelo adapter e recebe JSON estruturado. É "RAPTOR
  integrado", não "instalado ao lado".
- **Evidência de campo.** `raptor.py scan` num alvo com command injection gerou
  4 findings reais do Semgrep num SARIF de 3,2 MB — o fixture de teste é a saída
  real, e o número (3,2 MB para 6 linhas) confirmou a necessidade dos tetos de
  saída.

## Blockers externos (não adiam trabalho interno — são de plataforma/licença)

```
BLOCKER-ID=RAPTOR-PLAT-1
TYPE=BLOCKED_BY_PLATFORM_SECURITY
COMPONENT=sandbox de execução não confiável (fuzz/exploit/binary/crash/frida)
REASON=sandbox do RAPTOR é Linux(namespaces/Landlock/seccomp)+macOS(Seatbelt); zero Windows
WHAT_WAS_VERIFIED=core/sandbox sem ramo win32; docs/sandbox.md sem seção Windows
EXACT_REQUIREMENT_TO_UNBLOCK=WSL2 ou container Linux 3.12+ no ambiente do usuário
```
```
BLOCKER-ID=RAPTOR-LIC-1
TYPE=BLOCKED_BY_LICENSE_CONSTRAINT
COMPONENT=CodeQL
REASON=GitHub CodeQL Terms proíbem uso comercial; provider opcional desligado por padrão
```
```
BLOCKER-ID=RAPTOR-DEVICE-1
TYPE=BLOCKED_BY_PLATFORM_SECURITY
COMPONENT=Security Studio UI + packaging NSIS + installed-app smoke
REASON=exigem build/execução no Windows do usuário; não reproduzíveis no cloud
EXACT_REQUIREMENT_TO_UNBLOCK=rodar as waves 8/12/14 na máquina do usuário
```

## Não abandonado (missão anterior)

A finalização do Hermes segue em `audit/AUTONOMOUS_EXECUTION_STATE.md` e
`audit/FINAL_THREE_AGENT_REVIEW.md`. O fix loop das três auditorias foi commitado
(`7e51f88`). O RAPTOR é escopo ADICIONAL, não substituto.
