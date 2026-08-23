"""Envio: SENT só com confirmação real; rate-limit e anti-loop com teto real."""

import pytest

from whatsapp_provider.sending import (
    AntiLoopGuard,
    InvalidSendTransition,
    OutgoingMessage,
    OutgoingState,
    RateLimiter,
)


def test_sent_requires_a_real_message_id():
    m = OutgoingMessage(session_id="s1", chat_id="5511@c.us", text="oi")
    m.mark_sending()
    with pytest.raises(InvalidSendTransition, match="MessageId"):
        m.mark_sent("")  # sem id não é enviado
    m.mark_sent("TRUE_ID_123")
    assert m.state == OutgoingState.SENT
    assert m.message_id == "TRUE_ID_123"


def test_cannot_mark_sent_without_sending():
    m = OutgoingMessage(session_id="s1", chat_id="5511@c.us", text="oi")
    with pytest.raises(InvalidSendTransition):
        m.mark_sent("ID")  # pulou SENDING


def test_failed_can_retry():
    m = OutgoingMessage(session_id="s1", chat_id="5511@c.us", text="oi")
    m.mark_sending()
    m.mark_failed("timeout")
    assert m.state == OutgoingState.FAILED
    m._transition(OutgoingState.QUEUED)  # retry
    assert m.state == OutgoingState.QUEUED


def test_rate_limiter_blocks_burst():
    rl = RateLimiter(max_per_window=3, window_seconds=60)
    assert all(rl.allow("s1", now=1.0) for _ in range(3))
    assert rl.allow("s1", now=1.0) is False  # 4ª na janela: barrada


def test_rate_limiter_recovers_after_window():
    rl = RateLimiter(max_per_window=2, window_seconds=10)
    assert rl.allow("s1", now=1.0)
    assert rl.allow("s1", now=2.0)
    assert rl.allow("s1", now=3.0) is False
    assert rl.allow("s1", now=20.0) is True  # janela passou


def test_rate_limiter_is_per_session():
    rl = RateLimiter(max_per_window=1, window_seconds=60)
    assert rl.allow("s1", now=1.0)
    assert rl.allow("s2", now=1.0)  # sessão B não herda o limite de A


def test_anti_loop_never_replies_to_own_message():
    # A defesa central contra loop: não responder à própria resposta.
    g = AntiLoopGuard()
    assert g.should_reply(chat_id="c1", from_me=True) is False


def test_anti_loop_caps_replies_per_chat():
    g = AntiLoopGuard(max_consecutive=3, window_seconds=30)
    results = [g.should_reply(chat_id="c1", from_me=False, now=1.0) for _ in range(5)]
    assert results[:3] == [True, True, True]
    assert results[3:] == [False, False]  # tempestade barrada


def test_anti_loop_is_per_chat():
    g = AntiLoopGuard(max_consecutive=1, window_seconds=30)
    assert g.should_reply(chat_id="c1", from_me=False, now=1.0)
    assert g.should_reply(chat_id="c2", from_me=False, now=1.0)  # chat B independente
