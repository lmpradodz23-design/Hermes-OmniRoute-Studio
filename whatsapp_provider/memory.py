"""Memória do WhatsApp — a fronteira única entre evento recebido e persistência.

Nada de uma conversa de WhatsApp chega à memória do Hermes sem passar por aqui.
A regra é dura e verificável: o registro de memória NUNCA contém segredo, token,
apiKey, cookie, QR (dataURL) nem bytes de mídia. O que fica é o mínimo para o
agente lembrar do contexto — texto redigido e limitado, mais proveniência.

Reusa a disciplina de redação de `easyapi.redact_for_log` (dataURL primeiro,
depois key=value sensível) e adiciona: descarte de chaves sensíveis em metadata,
teto de tamanho do texto, e uma verificação `assert_no_secrets` que falha fechado
se algum resíduo sensível escapar.

Puro Python. A persistência real (SQLite/vetor/etc.) é do core; este módulo só
produz o registro seguro que ele pode guardar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .easyapi import redact_for_log
from .events import NormalizedEvent


# Chaves que nunca entram na metadata persistida.
SENSITIVE_KEYS = frozenset({
    "token", "api_key", "apikey", "x-api-key", "cookie", "qr", "qrcode",
    "session", "session_token", "password", "passwd", "secret",
    "authorization", "bearer", "wa_api_key", "auth",
})

# Teto do texto guardado — memória de longa duração não é dump ilimitado.
MAX_STORED_TEXT = 8192

# Padrões que, se sobrarem no texto redigido, indicam vazamento — a verificação
# final falha fechado se algum aparecer.
_RESIDUAL_SECRET_PATTERNS = (
    re.compile(r"data:image/[a-z]+;base64,[A-Za-z0-9+/=]{16,}"),  # QR/mídia embutida
    # marcador sensível seguido de um valor que NÃO seja o placeholder já
    # redigido — pega vazamento real, ignora "[REDACTED]".
    re.compile(r"(?i)\b(?:api[_-]?key|token|bearer|secret)\b\s*[:=]\s*(?!\[REDACTED\])\S+"),
)


class MemoryLeakError(Exception):
    """Levantada quando um registro de memória contém material sensível."""


@dataclass
class MemoryRecord:
    event_id: str
    session_id: str
    provider: str
    chat_id: str
    sender: str
    kind: str            # tipo do evento (message, etc.) como string estável
    timestamp: float
    text: str            # redigido e limitado
    has_media: bool = False
    media_kind: str = ""  # image/video/... — nunca os bytes
    reply_to: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Proveniência: o registro nasceu de entrada não confiável. Persistir isso
    # deixa claro para quem ler depois que não é autoridade.
    untrusted: bool = True


class MemorySanitizer:
    """Converte NormalizedEvent → MemoryRecord seguro. Ponto único de entrada
    da memória."""

    def __init__(self, max_text: int = MAX_STORED_TEXT):
        self.max_text = max_text

    def to_record(self, event: NormalizedEvent) -> MemoryRecord:
        text = redact_for_log(event.text or "")
        if len(text) > self.max_text:
            text = text[: self.max_text]

        record = MemoryRecord(
            event_id=event.event_id,
            session_id=event.session_id,
            provider=event.provider,
            chat_id=event.chat_id,
            sender=event.sender,
            kind=event.type.value if hasattr(event.type, "value") else str(event.type),
            timestamp=event.timestamp,
            text=text,
            has_media=event.media is not None,
            media_kind=str((event.media or {}).get("kind", "")) if event.media else "",
            reply_to=event.reply_to,
            metadata=self.sanitize_metadata(event.metadata),
            untrusted=True,
        )
        # Falha fechado: nunca devolve um registro com resíduo sensível.
        assert_no_secrets(record)
        return record

    def sanitize_metadata(self, meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not meta:
            return {}
        clean: Dict[str, Any] = {}
        for key, value in meta.items():
            if str(key).lower() in SENSITIVE_KEYS:
                continue  # descarta a chave inteira
            if isinstance(value, str):
                clean[key] = redact_for_log(value)
            elif isinstance(value, (int, float, bool)) or value is None:
                clean[key] = value
            else:
                # estruturas aninhadas viram string redigida — não guardamos
                # blobs arbitrários na memória.
                clean[key] = redact_for_log(str(value))
        return clean


def assert_no_secrets(record: MemoryRecord) -> None:
    """Verificação final defensiva. Varre os campos textuais do registro por
    resíduos sensíveis e levanta MemoryLeakError se achar algum."""
    haystacks = [record.text]
    for value in record.metadata.values():
        if isinstance(value, str):
            haystacks.append(value)
    blob = "\n".join(haystacks)
    for pattern in _RESIDUAL_SECRET_PATTERNS:
        if pattern.search(blob):
            raise MemoryLeakError(
                f"resíduo sensível no registro de memória (event_id={record.event_id})"
            )
    # metadata nunca deve conter chave sensível.
    leaked_keys = {k for k in record.metadata if str(k).lower() in SENSITIVE_KEYS}
    if leaked_keys:
        raise MemoryLeakError(f"chaves sensíveis na metadata: {sorted(leaked_keys)}")
