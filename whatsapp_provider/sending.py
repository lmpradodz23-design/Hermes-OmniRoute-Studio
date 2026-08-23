"""Envio de mensagem — máquina de estados que não mente sobre entrega, e
rate-limit + anti-loop por sessão.

`SENT` só quando há confirmação real (o OpenWA retorna o MessageId do envio; o
ack de entrega/leitura vem depois por evento). Nunca marcar SENT no otimismo.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque, Dict, Optional


class OutgoingState(str, Enum):
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"


_ALLOWED = {
    OutgoingState.QUEUED: {OutgoingState.SENDING, OutgoingState.FAILED},
    OutgoingState.SENDING: {OutgoingState.SENT, OutgoingState.FAILED},
    OutgoingState.SENT: set(),
    OutgoingState.FAILED: {OutgoingState.QUEUED},  # retry
}


class InvalidSendTransition(Exception):
    pass


@dataclass
class OutgoingMessage:
    session_id: str
    chat_id: str
    text: str
    state: OutgoingState = OutgoingState.QUEUED
    message_id: str = ""          # preenchido só quando o OpenWA confirma
    error: str = ""
    created_at: float = field(default_factory=time.time)

    def mark_sending(self) -> None:
        self._transition(OutgoingState.SENDING)

    def mark_sent(self, message_id: str) -> None:
        # SENT exige o id real de retorno — sem id, não é enviado.
        if not message_id or not str(message_id).strip():
            raise InvalidSendTransition("SENT exige o MessageId real retornado pelo OpenWA")
        self._transition(OutgoingState.SENT)
        self.message_id = str(message_id)

    def mark_failed(self, error: str) -> None:
        self._transition(OutgoingState.FAILED)
        self.error = error

    def _transition(self, to: OutgoingState) -> None:
        if to not in _ALLOWED[self.state]:
            raise InvalidSendTransition(f"{self.state.value} -> {to.value} não permitido")
        self.state = to


class RateLimiter:
    """Janela deslizante por sessão. Protege contra loop de agente, retry storm
    e mass-send acidental. Não é 'quase ilimitado' — tem teto real."""

    def __init__(self, max_per_window: int = 20, window_seconds: float = 60.0):
        self.max_per_window = max_per_window
        self.window_seconds = window_seconds
        self._events: Dict[str, Deque[float]] = {}

    def allow(self, session_id: str, *, now: Optional[float] = None) -> bool:
        t = now if now is not None else time.time()
        q = self._events.setdefault(session_id, deque())
        while q and t - q[0] > self.window_seconds:
            q.popleft()
        if len(q) >= self.max_per_window:
            return False
        q.append(t)
        return True


class AntiLoopGuard:
    """Impede o loop bot→responde→recebe a própria resposta→responde de novo.

    Duas defesas: (1) nunca responder a uma mensagem cujo remetente é a própria
    sessão (fromMe); (2) teto de respostas consecutivas para o mesmo chat numa
    janela curta — mesmo com remetentes distintos, uma tempestade de respostas
    para o mesmo chat é barrada.
    """

    def __init__(self, max_consecutive: int = 5, window_seconds: float = 30.0):
        self.max_consecutive = max_consecutive
        self.window_seconds = window_seconds
        self._replies: Dict[str, Deque[float]] = {}

    def should_reply(self, *, chat_id: str, from_me: bool, now: Optional[float] = None) -> bool:
        # (1) nunca responder à própria mensagem.
        if from_me:
            return False
        t = now if now is not None else time.time()
        q = self._replies.setdefault(chat_id, deque())
        while q and t - q[0] > self.window_seconds:
            q.popleft()
        # (2) teto de respostas por chat na janela.
        if len(q) >= self.max_consecutive:
            return False
        q.append(t)
        return True
