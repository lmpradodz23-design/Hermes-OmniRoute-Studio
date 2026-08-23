"""Normalização de eventos — do formato OpenWA para um contrato estável do
Hermes, com deduplicação por ID real.

O resto do Hermes NUNCA vê o formato bruto do OpenWA. Vê `NormalizedEvent`. E
toda mensagem recebida carrega `untrusted=True` — é dado a ser processado, não
instrução a ser obedecida.

Dedup por `message.id` (o campo estável que a auditoria confirmou): o WhatsApp
Web reentrega eventos, e processar a mesma mensagem duas vezes é o caminho para
resposta dupla e loop de bot.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class EventType(str, Enum):
    MESSAGE = "message"
    ACK = "ack"
    STATE = "state"
    GROUP = "group"
    DISCONNECT = "disconnect"
    SESSION_UPDATE = "session_update"
    UNKNOWN = "unknown"


# Mapa dos eventos REAIS do OpenWA (confirmados na auditoria) → tipo Hermes.
_OPENWA_EVENT_MAP = {
    "message.received": EventType.MESSAGE,
    "message.any": EventType.MESSAGE,
    "onMessage": EventType.MESSAGE,
    "onAnyMessage": EventType.MESSAGE,
    "ack.changed": EventType.ACK,
    "onAck": EventType.ACK,
    "session.state.changed": EventType.STATE,
    "onStateChanged": EventType.STATE,
    "session.logout": EventType.SESSION_UPDATE,
    "onLogout": EventType.SESSION_UPDATE,
    "call.incoming": EventType.UNKNOWN,  # existe no transport, não no cliente tipado
}


@dataclass
class NormalizedEvent:
    """Contrato estável do Hermes. Não expõe o formato OpenWA."""

    event_id: str
    provider: str
    session_id: str
    type: EventType
    timestamp: float
    chat_id: str = ""
    sender: str = ""
    recipient: str = ""
    text: str = ""
    media: Optional[Dict[str, Any]] = None
    reply_to: str = ""
    ack: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Toda mensagem recebida é entrada não confiável. Nunca é autoridade.
    untrusted: bool = True


def normalize_openwa_event(
    raw: Dict[str, Any], *, session_id: str, now: Optional[float] = None
) -> NormalizedEvent:
    """Converte um evento bruto do OpenWA em NormalizedEvent.

    Aceita tanto o formato de evento nomeado (v5: {event, data}) quanto o
    payload de mensagem direto (v4 onMessage). Campos ausentes viram vazios —
    nunca inventados.
    """
    ts = now if now is not None else time.time()
    ev_name = str(raw.get("event") or raw.get("type") or "onMessage")
    ev_type = _OPENWA_EVENT_MAP.get(ev_name, EventType.UNKNOWN)
    data = raw.get("data") if isinstance(raw.get("data"), dict) else raw

    # id estável: message.id para mensagens; para ack, o messageId.
    raw_id = (
        data.get("id")
        or data.get("messageId")
        or raw.get("id")
        or ""
    )
    event_id = str(raw_id) if raw_id else f"noid:{ev_name}:{ts}"

    ack_val = None
    if ev_type == EventType.ACK:
        try:
            ack_val = int(data.get("ack")) if data.get("ack") is not None else None
        except (TypeError, ValueError):
            ack_val = None

    media = None
    if data.get("mimetype") or data.get("isMedia") or data.get("type") in ("image", "video", "audio", "document", "ptt", "sticker"):
        media = {
            "mimetype": str(data.get("mimetype") or ""),
            "kind": str(data.get("type") or ""),
            "filename": str(data.get("filename") or ""),
        }

    return NormalizedEvent(
        event_id=event_id,
        provider="openwa",
        session_id=session_id,
        type=ev_type,
        timestamp=ts,
        chat_id=str(data.get("chatId") or data.get("from") or ""),
        sender=str(data.get("author") or data.get("sender", {}).get("id") if isinstance(data.get("sender"), dict) else data.get("from") or ""),
        recipient=str(data.get("to") or ""),
        text=str(data.get("body") or data.get("content") or "") if ev_type == EventType.MESSAGE else "",
        media=media,
        reply_to=str(data.get("quotedMsgId") or ""),
        ack=ack_val,
        metadata={"openwa_event": ev_name},
    )


class EventDeduper:
    """Dedup por event_id, com janela limitada (LRU) para não crescer sem fim.

    O WhatsApp Web reentrega eventos; sem dedup, um bot responde a mesma
    mensagem duas vezes. A janela é limitada porque guardar todo id para sempre
    é um vazamento de memória num runtime de longa duração.
    """

    def __init__(self, max_ids: int = 10_000):
        self.max_ids = max_ids
        self._seen: "OrderedDict[str, float]" = OrderedDict()

    def is_duplicate(self, event: NormalizedEvent) -> bool:
        """True se já vimos este event_id. Registra o id como visto."""
        # ids sintéticos (sem id real) nunca deduplicam — não temos como saber.
        if event.event_id.startswith("noid:"):
            return False
        if event.event_id in self._seen:
            self._seen.move_to_end(event.event_id)
            return True
        self._seen[event.event_id] = event.timestamp
        if len(self._seen) > self.max_ids:
            self._seen.popitem(last=False)  # descarta o mais antigo
        return False
