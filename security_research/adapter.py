"""RAPTOR adapter — a única superfície que conhece o RAPTOR.

Baixo acoplamento por design: o resto do Hermes fala com `SecurityEngine`
(engine.py), que fala com esta classe. Trocar/atualizar/desabilitar o RAPTOR é
mexer só aqui. O adapter invoca os MODOS PLANOS do RAPTOR
(`describe`, `scan`, `sca`, `analyze`) — os que rodam sem uma sessão Claude Code
e emitem JSON/SARIF (ver docs/RAPTOR_INTEGRATION_ARCHITECTURE.md §2).

Os modos que executam conteúdo não confiável (`fuzz`, `exploit`, `crash`,
`cve-env`, `frida`, `binary`) são gated por `runtime.detect_sandbox()`: sem
isolamento real, retornam BLOCKED_BY_PLATFORM_SECURITY em vez de rodar sem
contenção.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

from .boundary import AuthorizedTarget
from .permissions import Capability, CapabilityDenied, GrantSet
from .runtime import (
    ExecResult,
    SandboxCapabilities,
    detect_sandbox,
    run_argv,
)


class RaptorMode(str, Enum):
    DESCRIBE = "describe"      # read-only preflight, sem sandbox
    SCAN = "scan"             # scanner estático (semgrep), sem exec de alvo
    SCA = "sca"               # supply-chain
    ANALYZE = "analyze"       # consome SARIF
    # Modos que EXECUTAM conteúdo não confiável — exigem sandbox real:
    FUZZ = "fuzz"
    BINARY = "binary"
    EXPLOIT = "exploit"
    CRASH = "crash-analysis"
    FRIDA = "frida"


# Modos que executam conteúdo não confiável e exigem isolamento comprovado.
_EXEC_UNTRUSTED = {
    RaptorMode.FUZZ,
    RaptorMode.BINARY,
    RaptorMode.EXPLOIT,
    RaptorMode.CRASH,
    RaptorMode.FRIDA,
}

# Capacidade mínima que cada modo exige.
_MODE_CAPABILITY = {
    RaptorMode.DESCRIBE: Capability.READ_PROJECT,
    RaptorMode.SCAN: Capability.EXECUTE_SCANNER,
    RaptorMode.SCA: Capability.EXECUTE_SCANNER,
    RaptorMode.ANALYZE: Capability.READ_PROJECT,
    RaptorMode.FUZZ: Capability.FUZZ,
    RaptorMode.BINARY: Capability.EXECUTE_BINARY,
    RaptorMode.EXPLOIT: Capability.GENERATE_POC,
    RaptorMode.CRASH: Capability.EXECUTE_BINARY,
    RaptorMode.FRIDA: Capability.EXECUTE_BINARY,
}


class RaptorUnavailable(Exception):
    pass


class PlatformSecurityBlocked(Exception):
    def __init__(self, mode: RaptorMode, detail: str):
        self.mode = mode
        self.detail = detail
        super().__init__(f"BLOCKED_BY_PLATFORM_SECURITY: {mode.value} — {detail}")


@dataclass
class RaptorInfo:
    available: bool
    entrypoint: Optional[str]
    version: Optional[str]
    detail: str


class RaptorAdapter:
    """Invoca o RAPTOR por argv, dentro do alvo autorizado.

    `raptor_root` é onde o RAPTOR foi instalado (checkout isolado / vendored,
    NUNCA espalhado no core do Hermes). `python` é o interpretador que roda
    `raptor.py`.
    """

    def __init__(
        self,
        raptor_root: Optional[str],
        *,
        python: str = "python3",
        sandbox: Optional[SandboxCapabilities] = None,
    ):
        self.raptor_root = Path(raptor_root) if raptor_root else None
        self.python = python
        self.sandbox = sandbox or detect_sandbox()

    # ── descoberta / preflight ────────────────────────────────────────────

    def info(self) -> RaptorInfo:
        if not self.raptor_root or not (self.raptor_root / "raptor.py").is_file():
            return RaptorInfo(False, None, None, "raptor.py não encontrado no raptor_root")
        if not shutil.which(self.python):
            return RaptorInfo(False, str(self.raptor_root), None, f"interpretador ausente: {self.python}")
        return RaptorInfo(True, str(self.raptor_root / "raptor.py"), None, "disponível")

    def _entry(self) -> List[str]:
        info = self.info()
        if not info.available:
            raise RaptorUnavailable(info.detail)
        return [self.python, str(self.raptor_root / "raptor.py")]

    def _guard_mode(self, mode: RaptorMode, grants: GrantSet) -> None:
        # 1. capacidade concedida?
        grants.require(_MODE_CAPABILITY[mode])
        # 2. se executa conteúdo não confiável, exige sandbox real.
        if mode in _EXEC_UNTRUSTED and not self.sandbox.can_isolate_untrusted_exec:
            raise PlatformSecurityBlocked(mode, self.sandbox.detail)

    # ── modos planos (rodam aqui, sem Claude Code) ────────────────────────

    def describe(self, target: AuthorizedTarget, grants: GrantSet, *, timeout: float = 120) -> dict:
        """`raptor.py describe --target <root> --json` — preflight read-only."""
        self._guard_mode(RaptorMode.DESCRIBE, grants)
        argv = self._entry() + ["describe", "--target", str(target.root), "--json"]
        result = run_argv(argv, cwd=str(self.raptor_root), timeout=timeout)
        return _parse_json(result)

    def scan_argv(self, target: AuthorizedTarget, grants: GrantSet, out_dir: str) -> List[str]:
        """Monta (sem executar) o argv do scan. Exposto para teste do contrato.

        `--no-codeql` é explícito: CodeQL tem restrição de uso comercial
        (docs/RAPTOR_LICENSE_AUDIT.md) e fica desligado por padrão.
        """
        self._guard_mode(RaptorMode.SCAN, grants)
        return self._entry() + [
            "scan",
            "--repo",
            str(target.root),
            "--no-codeql",
            "--out",
            str(out_dir),
        ]

    def run_scan(
        self, target: AuthorizedTarget, grants: GrantSet, out_dir: str, *, timeout: float = 600
    ) -> ExecResult:
        argv = self.scan_argv(target, grants, out_dir)
        return run_argv(argv, cwd=str(self.raptor_root), timeout=timeout)


def _parse_json(result: ExecResult) -> dict:
    if result.timed_out:
        raise RaptorUnavailable("RAPTOR excedeu o timeout")
    try:
        return json.loads(result.stdout.decode("utf-8", "replace"))
    except json.JSONDecodeError as exc:
        raise RaptorUnavailable(f"saída do RAPTOR não é JSON: {exc}") from exc
