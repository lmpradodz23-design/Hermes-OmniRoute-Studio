# Security Research — guia do módulo

O Security Research é o motor de DevSecOps do Hermes OmniRoute Studio. Ele
concentra capacidades do RAPTOR compatíveis com o produto, sempre atrás de um
adapter, com o Hermes no controle de missão, autorização e UX.

Este documento descreve o **comportamento real** do que está implementado. O que
ainda depende do dispositivo Windows está marcado como tal — nada aqui é
apresentado como pronto sem ser.

## O princípio

Código analisado, README, saída de scanner, SARIF e saída de LLM são **entrada
não confiável**. Nada disso vira instrução ou comando automaticamente. Um
finding de scanner é um **candidato**, não uma vulnerabilidade confirmada — a
confirmação exige evidência, e só a máquina de estados pode promovê-lo.

Três níveis de evidência, separados de propósito: `FACT` (o scanner disse),
`INFERENCE` (deduzido de dados), `HYPOTHESIS` (especulação). Um finding
confirmado precisa de ao menos um FACT reproduzível. Um LLM não inventa a
evidência ausente.

## Fluxo (modos planos, disponíveis hoje)

```
Selecionar projeto (AUTHORIZED_SECURITY_TARGET)
   ↓  describe  — preflight read-only, sem sandbox
   ↓  scan      — Semgrep via RAPTOR, emite SARIF
   ↓  normalize — SARIF → Finding[] dentro da fronteira
   ↓  dedupe    — fingerprint estável (scanner+regra+arquivo+sink)
   ↓  Findings  — todos CANDIDATE
   ↓  validate  — CANDIDATE → VALIDATING → CONFIRMED (exige FACT)
   ↓  patch     — CONFIRMED → FIXING → (teste) → FIXED  (nunca pula etapa)
```

## Estados de finding

`CANDIDATE · VALIDATING · CONFIRMED · FALSE_POSITIVE · DISPUTED · FIXING ·
FIXED · REGRESSION_FAILED · BLOCKED`

Transições fora da máquina são recusadas. `FIXED` só depois de `FIXING`;
`CONFIRMED` só com evidência FACT; `FALSE_POSITIVE` é terminal mas o finding
**nunca é apagado** — o histórico é preservado.

## Estados da UI para capacidades

`AVAILABLE · EXPERIMENTAL · UNAVAILABLE · DEPENDENCY_REQUIRED`

Recurso upstream imaturo (alpha/beta/experimental) nunca é apresentado como
produção. Semgrep ausente → as operações de scan ficam `DEPENDENCY_REQUIRED`, e
o resto (histórico, threat model, relatórios) segue utilizável.

## Matriz de capacidades (mínimo privilégio)

| capacidade | default | confirmação | sandbox | rede | escrita | risco |
|---|---|---|---|---|---|---|
| read_project | concedida | não | não | não | não | baixo |
| execute_scanner | concedida | não | não | não | não | médio |
| network_lookup | negada | sim | não | sim | não | médio |
| write_project | negada | sim | não | não | sim | médio |
| execute_binary | negada | sim | **sim** | não | não | alto |
| fuzz | negada | sim | **sim** | não | sim | alto |
| generate_poc | negada | sim | **sim** | não | não | alto |
| apply_patch | negada | sim | não | não | sim | alto |
| shell | negada | sim | **sim** | não | sim | alto |
| ssh | negada | sim | não | sim | sim | alto |
| cron | negada | sim | não | não | não | médio |

O default é read-only + scan estático local. Tudo que executa alvo, escreve, faz
rede ou gera PoC exige decisão explícita; o que executa conteúdo não confiável
exige sandbox real (que no Windows nativo não existe — ver arquitetura).

## Defesas, e onde elas moram

- **Path traversal** → `boundary.py`. Todo caminho (de scanner, SARIF, LLM)
  passa por `AuthorizedTarget.resolve`, que rejeita `..`, absolutos, drives/UNC
  Windows, NUL bytes, e symlinks internos apontando para fora (checado após
  `realpath`). Testado em `tests/security_research/test_boundary.py`.
- **Command injection** → `runtime.run_argv`, `shell=False` sempre. Nome de
  projeto, caminho, args de scanner entram como tokens de argv, nunca numa
  string de shell.
- **SARIF hostil** → `sarif.py`. Tamanho máximo checado antes de parsear, versão
  e estrutura validadas, resultados limitados, uri resolvido dentro da fronteira.
- **Output DoS** → `runtime`, tetos de stdout/stderr (um scan de 6 linhas gerou
  3,2 MB de SARIF; a proteção é real, não teórica).
- **Verde artificial** → `findings`, máquina de estados que recusa promover sem
  evidência.

## Capacidades por status na integração

Modos planos, integrados e testados (o adapter os invoca por argv):
`describe`, `scan` (Semgrep), `sca`, `analyze`.

Modos de execução não confiável — gated por plataforma
(`BLOCKED_BY_PLATFORM_SECURITY` sem WSL2/container):
`fuzz`, `binary`, `exploit`, `crash-analysis`, `frida`.

Workflows agênticos (dependem de sessão Claude Code no upstream) —
`NOT_INTEGRATED_BY_DESIGN` neste estágio, roteáveis via OmniRoute no futuro:
`audit`, `understand`, `validate`, `patch`, `oss-forensics`.

CodeQL — `BLOCKED_BY_LICENSE_CONSTRAINT` (uso comercial), provider opcional
desligado por padrão.

## O que ainda depende do dispositivo Windows

Security Studio UI (Electron), packaging NSIS, smoke do app instalado, e o
sandbox real de execução não confiável. Ver
`docs/RAPTOR_INTEGRATION_ARCHITECTURE.md`.
