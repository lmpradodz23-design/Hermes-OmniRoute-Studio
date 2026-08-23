"""Máquina de estados de sessão WhatsApp — estados honestos, sem mentira.

O ponto central: `CONNECTED` só depois de autenticação real; `SENT` (em
sending.py) só depois de confirmação real. A UI reflete o estado da sessão, e
o estado nunca pula etapa nem finge conexão.

Ciclo (do prompt de integração §14):

  DISCONNECTED → STARTING → QR_REQUIRED → AUTHENTICATING → CONNECTED
                                              ↑                │
                                        RECONNECTING ←── DEGRADED
  CONNECTED/DEGRADED → LOGGED_OUT · qualquer → FAILED
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Set


class SessionState(str, Enum):
    DISCONNECTED = "disconnected"
    STARTING = "starting"
    QR_REQUIRED = "qr_required"
    AUTHENTICATING = "authenticating"
    CONNECTED = "connected"
    DEGRADED = "degraded"
    RECONNECTING = "reconnecting"
    FAILED = "failed"
    LOGGED_OUT = "logged_out"


_ALLOWED: Dict[SessionState, Set[SessionState]] = {
    SessionState.DISCONNECTED: {SessionState.STARTING},
    SessionState.STARTING: {
        SessionState.QR_REQUIRED,
        SessionState.AUTHENTICATING,  # sessão restaurada, sem QR
        SessionState.CONNECTED,       # restauração direta
        SessionState.FAILED,
    },
    SessionState.QR_REQUIRED: {
        SessionState.QR_REQUIRED,     # QR reemitido ao expirar
        SessionState.AUTHENTICATING,
        SessionState.FAILED,
        SessionState.DISCONNECTED,    # cancelado
    },
    SessionState.AUTHENTICATING: {
        SessionState.CONNECTED,
        SessionState.QR_REQUIRED,     # QR expirou durante auth
        SessionState.FAILED,
    },
    SessionState.CONNECTED: {
        SessionState.DEGRADED,
        SessionState.RECONNECTING,
        SessionState.LOGGED_OUT,
        SessionState.DISCONNECTED,
        SessionState.FAILED,
    },
    SessionState.DEGRADED: {
        SessionState.CONNECTED,
        SessionState.RECONNECTING,
        SessionState.LOGGED_OUT,
        SessionState.FAILED,
    },
    SessionState.RECONNECTING: {
        SessionState.CONNECTED,
        SessionState.DEGRADED,
        SessionState.FAILED,
        SessionState.LOGGED_OUT,
    },
    SessionState.FAILED: {SessionState.STARTING},        # retry manual
    SessionState.LOGGED_OUT: {SessionState.STARTING},    # novo login
}


class InvalidSessionTransition(Exception):
    pass


class SessionStateMachine:
    """Rastreia o estado de UMA sessão. Transição fora do mapa é recusada.

    `can_send` é a pergunta que o resto do módulo faz antes de aceitar um envio:
    só uma sessão realmente conectada pode mandar mensagem.
    """

    def __init__(self, session_id: str):
        if not session_id or not session_id.strip():
            raise ValueError("session_id vazio")
        self.session_id = session_id
        self.state = SessionState.DISCONNECTED
        self._history: list[SessionState] = [self.state]

    def transition(self, to: SessionState) -> None:
        if to not in _ALLOWED[self.state]:
            raise InvalidSessionTransition(
                f"{self.session_id}: {self.state.value} -> {to.value} não permitido"
            )
        self.state = to
        self._history.append(to)

    @property
    def can_send(self) -> bool:
        # DEGRADED ainda envia (conexão instável, mas viva); RECONNECTING não.
        return self.state in (SessionState.CONNECTED, SessionState.DEGRADED)

    @property
    def is_terminal(self) -> bool:
        return self.state in (SessionState.FAILED, SessionState.LOGGED_OUT)

    @property
    def history(self) -> list[SessionState]:
        return list(self._history)
