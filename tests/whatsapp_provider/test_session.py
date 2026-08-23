"""Máquina de estados de sessão — estados honestos, sem conexão fingida."""

import pytest

from whatsapp_provider.session import (
    InvalidSessionTransition,
    SessionState,
    SessionStateMachine,
)


def test_starts_disconnected():
    assert SessionStateMachine("s1").state == SessionState.DISCONNECTED


def test_happy_path_qr_flow():
    m = SessionStateMachine("s1")
    m.transition(SessionState.STARTING)
    m.transition(SessionState.QR_REQUIRED)
    m.transition(SessionState.AUTHENTICATING)
    m.transition(SessionState.CONNECTED)
    assert m.can_send


def test_cannot_jump_straight_to_connected_from_disconnected():
    # "conexão fingida" — pular do zero para CONNECTED é recusado.
    m = SessionStateMachine("s1")
    with pytest.raises(InvalidSessionTransition):
        m.transition(SessionState.CONNECTED)


def test_cannot_send_while_reconnecting():
    m = SessionStateMachine("s1")
    for st in (SessionState.STARTING, SessionState.QR_REQUIRED, SessionState.AUTHENTICATING, SessionState.CONNECTED):
        m.transition(st)
    m.transition(SessionState.RECONNECTING)
    assert not m.can_send


def test_degraded_can_still_send():
    m = SessionStateMachine("s1")
    for st in (SessionState.STARTING, SessionState.AUTHENTICATING, SessionState.CONNECTED, SessionState.DEGRADED):
        m.transition(st)
    assert m.can_send


def test_qr_can_be_reissued():
    m = SessionStateMachine("s1")
    m.transition(SessionState.STARTING)
    m.transition(SessionState.QR_REQUIRED)
    m.transition(SessionState.QR_REQUIRED)  # expirou, reemitido
    assert m.state == SessionState.QR_REQUIRED


def test_restored_session_skips_qr():
    m = SessionStateMachine("s1")
    m.transition(SessionState.STARTING)
    m.transition(SessionState.CONNECTED)  # sessão restaurada, sem QR
    assert m.can_send


def test_logout_and_relogin():
    m = SessionStateMachine("s1")
    for st in (SessionState.STARTING, SessionState.AUTHENTICATING, SessionState.CONNECTED, SessionState.LOGGED_OUT):
        m.transition(st)
    assert m.is_terminal
    m.transition(SessionState.STARTING)  # novo login permitido
    assert m.state == SessionState.STARTING
