"""Política de resposta do agente — a barreira entre "mensagem recebida" e
"agente responde/age".

Mensagem do WhatsApp é UNTRUSTED_INPUT, mesmo de contato conhecido. Ela NUNCA
concede, por si só, poder para shell/filesystem/SSH/cron/envio massivo. Isto é
enforçado aqui, no ponto onde o candidato de resposta do agente é avaliado —
não no prompt.

Uma resposta só sai se: há permissão de envio, a sessão está online, o rate
limit permite, e o anti-loop permite (não é a própria mensagem do bot).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .capabilities import WhatsAppCapability, WhatsAppGrants
from .sending import AntiLoopGuard, RateLimiter
from .session import SessionState


class OutboundDecision(str, Enum):
    ALLOW = "allow"
    DENIED_NO_PERMISSION = "denied_no_permission"
    DENIED_OFFLINE = "denied_offline"
    DENIED_RATE_LIMIT = "denied_rate_limit"
    DENIED_LOOP = "denied_loop"
    NEEDS_CONFIRMATION = "needs_confirmation"


# Capacidades privilegiadas que uma mensagem recebida NUNCA pode acionar
# automaticamente — exigem human-in-the-loop, seja qual for o texto (§27).
PRIVILEGED_ACTIONS = frozenset({
    "shell", "filesystem_write", "ssh", "git_destructive",
    "cron_persistent", "bulk_send", "data_export",
})


@dataclass
class OutboundContext:
    session_id: str
    chat_id: str
    session_state: SessionState
    from_me: bool
    grants: WhatsAppGrants
    requested_privileged_action: Optional[str] = None
    requires_confirmation: bool = False
    confirmed: bool = False


class OutboundPolicy:
    """Decide se o candidato de resposta do agente pode sair."""

    def __init__(self, rate_limiter: Optional[RateLimiter] = None, anti_loop: Optional[AntiLoopGuard] = None):
        self.rate_limiter = rate_limiter or RateLimiter()
        self.anti_loop = anti_loop or AntiLoopGuard()

    def evaluate(self, ctx: OutboundContext, *, now: Optional[float] = None) -> OutboundDecision:
        # 0. ação privilegiada pedida por mensagem recebida → NUNCA automática.
        if ctx.requested_privileged_action in PRIVILEGED_ACTIONS:
            if not ctx.confirmed:
                return OutboundDecision.NEEDS_CONFIRMATION

        # 1. anti-loop: nunca responder à própria mensagem, nem entrar em
        #    tempestade para o mesmo chat.
        if not self.anti_loop.should_reply(chat_id=ctx.chat_id, from_me=ctx.from_me, now=now):
            return OutboundDecision.DENIED_LOOP

        # 2. permissão de envio.
        if WhatsAppCapability.SEND not in ctx.grants.granted:
            return OutboundDecision.DENIED_NO_PERMISSION

        # 3. sessão online.
        if ctx.session_state not in (SessionState.CONNECTED, SessionState.DEGRADED):
            return OutboundDecision.DENIED_OFFLINE

        # 4. confirmação exigida por política.
        if ctx.requires_confirmation and not ctx.confirmed:
            return OutboundDecision.NEEDS_CONFIRMATION

        # 5. rate limit.
        if not self.rate_limiter.allow(ctx.session_id, now=now):
            return OutboundDecision.DENIED_RATE_LIMIT

        return OutboundDecision.ALLOW
