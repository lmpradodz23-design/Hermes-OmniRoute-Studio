"""Validação de entradas — IDs, texto, mídia. Toda entrada da UI/agente/mensagem
é hostil até prova em contrário.

A defesa de path traversal de mídia reusa a fronteira do módulo de segurança
(`security_research.boundary`) — um só dono para "caminho não escapa da raiz
autorizada", em vez de duas implementações que divergem.
"""

from __future__ import annotations

import re
from pathlib import Path

# chat id do WhatsApp: dígitos + sufixo @c.us (contato) ou @g.us (grupo).
# Formato real do OpenWA/WhatsApp Web.
_CHAT_ID = re.compile(r"^[0-9]{5,20}@(c\.us|g\.us)$")
# Também aceita broadcast e status, mas NUNCA algo com metacaractere.
_CHAT_ID_SPECIAL = re.compile(r"^(status@broadcast|[0-9]{5,20}-[0-9]{5,20}@g\.us)$")

MAX_TEXT_LEN = 65536  # WhatsApp corta bem antes, mas é o teto anti-DoS.


class WhatsAppValidationError(Exception):
    pass


def validate_chat_id(raw: str) -> str:
    """Valida um chat/phone id. Recusa qualquer coisa com metacaractere —
    um id é dado, nunca fragmento de comando ou de caminho."""
    if not isinstance(raw, str) or not raw.strip():
        raise WhatsAppValidationError("chat id vazio")
    cid = raw.strip()
    if "\x00" in cid or any(c in cid for c in r"/\;|&`$<>" + "\n\r"):
        raise WhatsAppValidationError(f"chat id com caractere ilegal: {cid!r}")
    if not (_CHAT_ID.match(cid) or _CHAT_ID_SPECIAL.match(cid)):
        raise WhatsAppValidationError(f"chat id em formato inválido: {cid!r}")
    return cid


def validate_text(raw: str) -> str:
    if not isinstance(raw, str):
        raise WhatsAppValidationError("texto não é string")
    if "\x00" in raw:
        raise WhatsAppValidationError("NUL byte no texto")
    if len(raw) > MAX_TEXT_LEN:
        raise WhatsAppValidationError(f"texto longo demais: {len(raw)} (máx {MAX_TEXT_LEN})")
    if not raw:
        raise WhatsAppValidationError("texto vazio")
    return raw


def validate_media_path(raw: str, *, allowed_root: str) -> Path:
    """Resolve um caminho de mídia DENTRO de uma raiz autorizada.

    Reusa a fronteira de segurança do RAPTOR: mídia enviada por caminho não
    pode escapar da pasta autorizada (path traversal → exfiltração de arquivo).
    """
    from security_research.boundary import AuthorizedTarget, ProjectBoundaryError

    try:
        target = AuthorizedTarget.create(allowed_root)
        return target.resolve(raw)
    except ProjectBoundaryError as exc:
        raise WhatsAppValidationError(f"caminho de mídia rejeitado: {exc}") from exc


# Allowlist de argumentos de browser (§50). A UI NUNCA passa args arbitrários;
# só estes, e nenhum que reduza sandbox.
_BROWSER_ARG_ALLOWLIST = frozenset({
    "--headless",
    "--no-first-run",
    "--disable-gpu",
    "--window-size",
})

# Flags que REDUZEM segurança — recusadas mesmo se alguém tentar allowlistar.
_BROWSER_ARG_DENYLIST = frozenset({
    "--no-sandbox",
    "--disable-web-security",
    "--disable-setuid-sandbox",
    "--allow-running-insecure-content",
    "--remote-debugging-port",
    "--remote-debugging-address",
})


def validate_browser_args(args: list[str]) -> list[str]:
    """Filtra args de browser por allowlist, recusando flags que enfraquecem o
    sandbox. Uma flag fora da allowlist é rejeitada, não ignorada em silêncio."""
    out = []
    for arg in args or []:
        head = arg.split("=", 1)[0]
        if head in _BROWSER_ARG_DENYLIST:
            raise WhatsAppValidationError(f"flag de browser insegura recusada: {head}")
        if head not in _BROWSER_ARG_ALLOWLIST:
            raise WhatsAppValidationError(f"flag de browser fora da allowlist: {head}")
        out.append(arg)
    return out
