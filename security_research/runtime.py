"""Runtime de execução do RAPTOR — argv-only, com limites, e a abstração de
sandbox que diz a verdade sobre a plataforma.

Duas verdades duras da auditoria do RAPTOR (docs/RAPTOR_INTEGRATION_ARCHITECTURE.md):

  1. Toda execução é por lista de argumentos (`argv`), NUNCA `shell=True` com
     interpolação. Nome de projeto, caminho, args de scanner: tudo entra como
     token de argv, jamais concatenado numa string de shell. É a defesa de
     command injection no ponto real de execução, não no prompt.

  2. O sandbox do RAPTOR é Linux (namespaces/Landlock/seccomp) + macOS
     (Seatbelt). NÃO existe sandbox nativo no Windows. `SandboxProvider` não
     finge o contrário: no Windows nativo, operações que executam conteúdo não
     confiável retornam BLOCKED_BY_PLATFORM_SECURITY, e o caminho suportado é
     WSL2/container Linux.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Sequence

# Tetos de saída — um scan de 6 linhas já gerou 3,2 MB de SARIF. Uma ferramenta
# hostil não pode derrubar o Hermes com gigabytes de stdout.
MAX_STDOUT_BYTES = 32 * 1024 * 1024
MAX_STDERR_BYTES = 4 * 1024 * 1024


class SandboxBackend(str, Enum):
    LINUX_NAMESPACES = "linux_namespaces"
    CONTAINER = "container"
    WSL2 = "wsl2"
    WINDOWS_RESTRICTED = "windows_restricted"
    NONE = "none"


class PlatformSecurityBlocked(Exception):
    """A operação exige isolamento que a plataforma atual não oferece."""


@dataclass
class SandboxCapabilities:
    backend: SandboxBackend
    can_isolate_untrusted_exec: bool
    detail: str


def detect_sandbox() -> SandboxCapabilities:
    """Descobre o melhor backend de sandbox REALMENTE disponível.

    Não declara capacidade que não tem. No Windows nativo sem WSL/Docker, o
    resultado é WINDOWS_RESTRICTED, que NÃO isola execução não confiável.
    """
    system = platform.system().lower()
    if system == "linux":
        # O sandbox do RAPTOR exige Python 3.12+ (os.unshare). Abaixo disso, o
        # namespaces-sandbox não sobe — reporta honestamente.
        if sys.version_info >= (3, 12):
            return SandboxCapabilities(
                SandboxBackend.LINUX_NAMESPACES, True, "user/net/pid/mount ns + Landlock + seccomp"
            )
        return SandboxCapabilities(
            SandboxBackend.NONE, False, "Linux mas Python < 3.12: namespaces-sandbox indisponível"
        )
    if system == "darwin":
        return SandboxCapabilities(
            SandboxBackend.CONTAINER if shutil.which("docker") else SandboxBackend.NONE,
            bool(shutil.which("docker")),
            "macOS: Seatbelt do RAPTOR roda no host; container para isolamento forte",
        )
    if system == "windows":
        if shutil.which("wsl"):
            return SandboxCapabilities(
                SandboxBackend.WSL2, True, "WSL2 disponível: caminho suportado no Windows"
            )
        if shutil.which("docker"):
            return SandboxCapabilities(
                SandboxBackend.CONTAINER, True, "Docker disponível: container Linux"
            )
        return SandboxCapabilities(
            SandboxBackend.WINDOWS_RESTRICTED,
            False,
            "Windows nativo sem WSL/Docker: sem sandbox para execução não confiável",
        )
    return SandboxCapabilities(SandboxBackend.NONE, False, f"plataforma desconhecida: {system}")


@dataclass
class ExecResult:
    argv: List[str]
    returncode: int
    stdout: bytes
    stderr: bytes
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    timed_out: bool = False
    cancelled: bool = False


class OutputLimitExceeded(Exception):
    pass


def _validate_argv(argv: Sequence[str]) -> List[str]:
    """Recusa argv não estruturado. Cada token tem que ser string sem NUL."""
    if not argv or not isinstance(argv, (list, tuple)):
        raise ValueError("argv precisa ser uma lista não vazia de strings")
    out = []
    for tok in argv:
        if not isinstance(tok, str):
            raise ValueError(f"token de argv não é string: {tok!r}")
        if "\x00" in tok:
            raise ValueError("NUL byte em token de argv")
        out.append(tok)
    return out


@dataclass
class ProcessHandle:
    """Rastreia um subprocesso: PID, cancelamento, e limites de saída."""

    proc: subprocess.Popen
    argv: List[str]
    cancelled: bool = field(default=False)

    @property
    def pid(self) -> int:
        return self.proc.pid

    def cancel(self) -> None:
        """Encerra o processo e sua árvore, sem deixar órfão."""
        self.cancelled = True
        if self.proc.poll() is not None:
            return
        try:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        except (ProcessLookupError, OSError):
            pass


def run_argv(
    argv: Sequence[str],
    *,
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
    timeout: float = 300.0,
    max_stdout: int = MAX_STDOUT_BYTES,
    max_stderr: int = MAX_STDERR_BYTES,
) -> ExecResult:
    """Executa um comando por argv, SEM shell, com timeout e tetos de saída.

    `shell=False` sempre. Não há caminho neste módulo que passe uma string para
    um shell — é a diferença entre "executable + argv[]" e
    "shell + input interpolado".
    """
    args = _validate_argv(argv)
    try:
        completed = subprocess.run(
            args,
            cwd=cwd,
            env=env,
            capture_output=True,
            timeout=timeout,
            shell=False,  # inegociável
        )
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or b""
        err = exc.stderr or b""
        return ExecResult(
            argv=args,
            returncode=124,
            stdout=out[:max_stdout],
            stderr=err[:max_stderr],
            stdout_truncated=len(out) > max_stdout,
            stderr_truncated=len(err) > max_stderr,
            timed_out=True,
        )
    out = completed.stdout or b""
    err = completed.stderr or b""
    return ExecResult(
        argv=args,
        returncode=completed.returncode,
        stdout=out[:max_stdout],
        stderr=err[:max_stderr],
        stdout_truncated=len(out) > max_stdout,
        stderr_truncated=len(err) > max_stderr,
    )
