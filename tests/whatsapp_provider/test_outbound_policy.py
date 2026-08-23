"""Testes da OutboundPolicy — a barreira entre "mensagem recebida" e "agente age".

Prova, no ponto de decisão (não no prompt):
  - ação privilegiada pedida por mensagem recebida NUNCA sai automática;
  - a ordem das barreiras (privileged → loop → permission → online → confirmation → rate);
  - cada DENIED_* dispara pela sua própria razão.
"""

import pytest

from whatsapp_provider.capabilities import WhatsAppCapability, WhatsAppGrants
from whatsapp_provider.outbound_policy import (
    OutboundContext,
    OutboundDecision,
    OutboundPolicy,
    PRIVILEGED_ACTIONS,
)
from whatsapp_provider.sending import AntiLoopGuard, RateLimiter
from whatsapp_provider.session import SessionState


def _send_grants() -> WhatsAppGrants:
    return WhatsAppGrants().with_granted(WhatsAppCapability.SEND)


def _ctx(**overrides) -> OutboundContext:
    base = dict(
        session_id="s1",
        chat_id="555199999999@c.us",
        session_state=SessionState.CONNECTED,
        from_me=False,
        grants=_send_grants(),
    )
    base.update(overrides)
    return OutboundContext(**base)


def test_happy_path_allows():
    policy = OutboundPolicy()
    assert policy.evaluate(_ctx(), now=0.0) is OutboundDecision.ALLOW


def test_privileged_action_needs_confirmation_even_with_send_grant():
    """Toda ação privilegiada listada exige human-in-the-loop, seja qual for o texto."""
    policy = OutboundPolicy()
    for action in PRIVILEGED_ACTIONS:
        decision = policy.evaluate(
            _ctx(requested_privileged_action=action, confirmed=False), now=0.0
        )
        assert decision is OutboundDecision.NEEDS_CONFIRMATION, action


def test_privileged_action_confirmed_can_proceed():
    policy = OutboundPolicy()
    decision = policy.evaluate(
        _ctx(requested_privileged_action="shell", confirmed=True), now=0.0
    )
    assert decision is OutboundDecision.ALLOW


def test_privileged_check_precedes_loop_and_permission():
    """Mesmo sem SEND e com from_me, uma ação privilegiada não-confirmada
    resolve como NEEDS_CONFIRMATION — a barreira privilegiada vem primeiro."""
    policy = OutboundPolicy()
    decision = policy.evaluate(
        _ctx(
            grants=WhatsAppGrants(),  # só READ
            from_me=True,
            requested_privileged_action="data_export",
            confirmed=False,
        ),
        now=0.0,
    )
    assert decision is OutboundDecision.NEEDS_CONFIRMATION


def test_from_me_is_denied_loop():
    policy = OutboundPolicy()
    assert policy.evaluate(_ctx(from_me=True), now=0.0) is OutboundDecision.DENIED_LOOP


def test_reply_storm_to_same_chat_is_denied_loop():
    policy = OutboundPolicy(anti_loop=AntiLoopGuard(max_consecutive=2, window_seconds=30.0))
    ctx = _ctx()
    assert policy.evaluate(ctx, now=0.0) is OutboundDecision.ALLOW
    assert policy.evaluate(ctx, now=0.1) is OutboundDecision.ALLOW
    assert policy.evaluate(ctx, now=0.2) is OutboundDecision.DENIED_LOOP


def test_no_send_grant_is_denied_no_permission():
    policy = OutboundPolicy()
    decision = policy.evaluate(_ctx(grants=WhatsAppGrants()), now=0.0)  # só READ
    assert decision is OutboundDecision.DENIED_NO_PERMISSION


@pytest.mark.parametrize(
    "state",
    [
        SessionState.DISCONNECTED,
        SessionState.QR_REQUIRED,
        SessionState.AUTHENTICATING,
        SessionState.RECONNECTING,
        SessionState.FAILED,
        SessionState.LOGGED_OUT,
    ],
)
def test_offline_states_are_denied_offline(state):
    policy = OutboundPolicy()
    assert policy.evaluate(_ctx(session_state=state), now=0.0) is OutboundDecision.DENIED_OFFLINE


@pytest.mark.parametrize("state", [SessionState.CONNECTED, SessionState.DEGRADED])
def test_connected_and_degraded_can_send(state):
    policy = OutboundPolicy()
    assert policy.evaluate(_ctx(session_state=state), now=0.0) is OutboundDecision.ALLOW


def test_requires_confirmation_without_confirmed_needs_confirmation():
    policy = OutboundPolicy()
    decision = policy.evaluate(_ctx(requires_confirmation=True, confirmed=False), now=0.0)
    assert decision is OutboundDecision.NEEDS_CONFIRMATION


def test_requires_confirmation_with_confirmed_allows():
    policy = OutboundPolicy()
    decision = policy.evaluate(_ctx(requires_confirmation=True, confirmed=True), now=0.0)
    assert decision is OutboundDecision.ALLOW


def test_rate_limit_exhaustion_is_denied_rate_limit():
    policy = OutboundPolicy(rate_limiter=RateLimiter(max_per_window=1, window_seconds=60.0))
    # cada chamada usa um chat distinto para não esbarrar no anti-loop
    assert policy.evaluate(_ctx(chat_id="1@c.us"), now=0.0) is OutboundDecision.ALLOW
    assert policy.evaluate(_ctx(chat_id="2@c.us"), now=0.0) is OutboundDecision.DENIED_RATE_LIMIT


def test_rate_limit_check_comes_after_offline_check():
    """Sessão offline resolve como OFFLINE mesmo com rate limit esgotado —
    a ordem impede vazar estado de rate para sessão que nem podia enviar."""
    policy = OutboundPolicy(rate_limiter=RateLimiter(max_per_window=0, window_seconds=60.0))
    decision = policy.evaluate(_ctx(session_state=SessionState.DISCONNECTED), now=0.0)
    assert decision is OutboundDecision.DENIED_OFFLINE


def test_privileged_actions_set_is_frozen():
    assert isinstance(PRIVILEGED_ACTIONS, frozenset)
    assert {"shell", "ssh", "filesystem_write", "bulk_send"} <= PRIVILEGED_ACTIONS
