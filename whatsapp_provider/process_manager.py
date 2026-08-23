"""Gerência do processo externo do OpenWA — ownership, restart com backoff, e a
distinção entre crash transitório e logout.

O Hermes só mata o que ele mesmo iniciou (`owned_by_hermes`). Restart nunca é
infinito: backoff exponencial com teto e janela. E logout/sessão inválida NÃO é
tratado como crash a ser reiniciado — reiniciar aí só geraria um novo QR em
loop.

Este módulo é a POLÍTICA (pura, testável). O spawn real do subprocesso é do
runtime do Hermes, que consome estas decisões — mantém o módulo testável sem
subir processo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RuntimeStatus(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    CRASHED = "crashed"
    LOGGED_OUT = "logged_out"   # não reinicia sozinho — exige novo QR
    GIVEN_UP = "given_up"       # excedeu o teto de restart


@dataclass
class RuntimeRecord:
    """Estado observável do processo (§17)."""

    pid: Optional[int] = None
    started_at: float = 0.0
    status: RuntimeStatus = RuntimeStatus.STOPPED
    exit_code: Optional[int] = None
    restart_count: int = 0
    last_error: str = ""
    owned_by_hermes: bool = False


class RestartPolicy:
    """Backoff exponencial com teto e janela. Nunca restart infinito (§18).

    `next_delay` cresce 2^n até `max_delay`; `should_restart` recusa depois de
    `max_restarts` na janela, e recusa sempre para logout (não é crash)."""

    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        max_restarts: int = 5,
        window_seconds: float = 300.0,
    ):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_restarts = max_restarts
        self.window_seconds = window_seconds
        self._restart_times: list[float] = []

    def _prune(self, now: float) -> None:
        self._restart_times = [t for t in self._restart_times if now - t <= self.window_seconds]

    def should_restart(self, *, status: RuntimeStatus, now: float) -> bool:
        # logout/sessão inválida não é crash: reiniciar só geraria QR em loop.
        if status == RuntimeStatus.LOGGED_OUT:
            return False
        if status != RuntimeStatus.CRASHED:
            return False
        self._prune(now)
        return len(self._restart_times) < self.max_restarts

    def record_restart(self, now: float) -> float:
        """Registra um restart e devolve o delay antes da próxima tentativa."""
        self._prune(now)
        n = len(self._restart_times)
        self._restart_times.append(now)
        return min(self.base_delay * (2 ** n), self.max_delay)


class ProcessManager:
    """Ownership do processo OpenWA. Só encerra o que é `owned_by_hermes`.

    Não faz spawn aqui — decide. O runtime do Hermes chama `on_started`/
    `on_exited` e pergunta `plan_restart`. Assim a política inteira é testável
    sem tocar em subprocesso real (§17-19)."""

    def __init__(self, policy: Optional[RestartPolicy] = None):
        self.record = RuntimeRecord()
        self.policy = policy or RestartPolicy()

    def on_started(self, pid: int, *, now: float) -> None:
        self.record.pid = pid
        self.record.started_at = now
        self.record.status = RuntimeStatus.RUNNING
        self.record.owned_by_hermes = True
        self.record.exit_code = None

    def on_exited(self, exit_code: int, *, logged_out: bool = False, now: float = 0.0) -> None:
        self.record.exit_code = exit_code
        self.record.pid = None
        if logged_out:
            self.record.status = RuntimeStatus.LOGGED_OUT
        elif exit_code == 0:
            self.record.status = RuntimeStatus.STOPPED
        else:
            self.record.status = RuntimeStatus.CRASHED
            self.record.last_error = f"exit {exit_code}"

    def can_kill(self) -> bool:
        """Só mata processo que o Hermes iniciou — nunca um browser do usuário."""
        return self.record.owned_by_hermes and self.record.pid is not None

    def plan_restart(self, *, now: float) -> Optional[float]:
        """Devolve o delay até o próximo restart, ou None se não deve reiniciar.

        Marca GIVEN_UP quando estoura o teto — recovery vira manual (§18)."""
        if not self.policy.should_restart(status=self.record.status, now=now):
            if self.record.status == RuntimeStatus.CRASHED:
                self.record.status = RuntimeStatus.GIVEN_UP
            return None
        delay = self.policy.record_restart(now)
        self.record.restart_count += 1
        return delay
