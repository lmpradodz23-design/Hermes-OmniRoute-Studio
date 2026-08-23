"""Superfície MCP do WhatsApp — allowlist explícita, nunca a API OpenWA inteira.

Cada tool declara: capacidade exigida, se muda estado, e o schema de entrada.
O dispatcher aplica, nesta ordem:

  1. a tool está na allowlist? (fora dela = recusada)
  2. a capacidade foi concedida? (gate no ponto de execução)
  3. o input valida? (schema rígido — reusa validation.py)
  4. a sessão permite? (envio numa sessão não autenticada NÃO retorna SUCCESS —
     retorna o estado real: NOT_AUTHENTICATED / QR_REQUIRED / SESSION_UNAVAILABLE)

Só depois disso a chamada chega ao provider. Sem sucesso falso: enquanto a
sessão real não estiver conectada, send_* devolve o estado, não um ack inventado.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional

from .capabilities import WhatsAppCapability, WhatsAppCapabilityDenied, WhatsAppGrants
from .provider import ProviderStatus, SendResult, WhatsAppProvider
from .session import SessionState
from .validation import WhatsAppValidationError, validate_chat_id, validate_media_path, validate_text


class ToolOutcome(str, Enum):
    OK = "ok"
    NOT_AUTHENTICATED = "not_authenticated"
    QR_REQUIRED = "qr_required"
    SESSION_UNAVAILABLE = "session_unavailable"
    DENIED = "denied"
    INVALID = "invalid"
    ERROR = "error"


@dataclass
class ToolResult:
    outcome: ToolOutcome
    data: Optional[Dict[str, Any]] = None
    message: str = ""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    capability: WhatsAppCapability
    mutates: bool
    needs_connected: bool   # exige sessão conectada para ter efeito real


# ── ALLOWLIST — só estas ferramentas, nunca a API OpenWA bruta ────────────
TOOL_ALLOWLIST: Dict[str, ToolSpec] = {
    "whatsapp.status":       ToolSpec("whatsapp.status", WhatsAppCapability.READ, False, False),
    "whatsapp.sessions":     ToolSpec("whatsapp.sessions", WhatsAppCapability.READ, False, False),
    "whatsapp.health":       ToolSpec("whatsapp.health", WhatsAppCapability.READ, False, False),
    "whatsapp.get_chats":    ToolSpec("whatsapp.get_chats", WhatsAppCapability.READ, False, True),
    "whatsapp.get_messages": ToolSpec("whatsapp.get_messages", WhatsAppCapability.READ, False, True),
    "whatsapp.connect":      ToolSpec("whatsapp.connect", WhatsAppCapability.MANAGE, True, False),
    "whatsapp.disconnect":   ToolSpec("whatsapp.disconnect", WhatsAppCapability.MANAGE, True, False),
    "whatsapp.send_text":    ToolSpec("whatsapp.send_text", WhatsAppCapability.SEND, True, True),
    "whatsapp.send_media":   ToolSpec("whatsapp.send_media", WhatsAppCapability.SEND_MEDIA, True, True),
}


def _state_outcome(state: SessionState) -> Optional[ToolOutcome]:
    """Mapeia estado de sessão para o motivo de NÃO poder agir. None = pode."""
    if state in (SessionState.CONNECTED, SessionState.DEGRADED):
        return None
    if state == SessionState.QR_REQUIRED:
        return ToolOutcome.QR_REQUIRED
    if state in (SessionState.LOGGED_OUT, SessionState.FAILED, SessionState.DISCONNECTED):
        return ToolOutcome.NOT_AUTHENTICATED
    return ToolOutcome.SESSION_UNAVAILABLE


class WhatsAppMcpDispatcher:
    """Roteia chamadas MCP para o provider, aplicando allowlist + capacidade +
    schema + estado de sessão. É a política central de autorização (§27 do
    prompt de integração): uma única porta, no ponto real de execução."""

    def __init__(self, provider: WhatsAppProvider, media_root: str = ""):
        self.provider = provider
        self.media_root = media_root

    def list_tools(self) -> list[str]:
        return sorted(TOOL_ALLOWLIST)

    def call(self, name: str, args: Dict[str, Any], grants: WhatsAppGrants) -> ToolResult:
        # 1. allowlist
        spec = TOOL_ALLOWLIST.get(name)
        if spec is None:
            return ToolResult(ToolOutcome.DENIED, message=f"ferramenta fora da allowlist: {name}")

        # 2. capacidade — no ponto de execução, não no prompt/renderer
        try:
            grants.require(spec.capability)
        except WhatsAppCapabilityDenied as exc:
            return ToolResult(ToolOutcome.DENIED, message=str(exc))

        # 3. schema
        try:
            clean = self._validate(name, args)
        except WhatsAppValidationError as exc:
            return ToolResult(ToolOutcome.INVALID, message=str(exc))

        # 4. estado de sessão — sem sucesso falso
        if spec.needs_connected:
            reason = _state_outcome(self.provider.get_status().state)
            if reason is not None:
                return ToolResult(reason, message=f"{name} indisponível: {reason.value}")

        # 5. executa
        try:
            return self._execute(name, clean)
        except Exception as exc:  # noqa: BLE001 — a fronteira converte tudo em resultado
            return ToolResult(ToolOutcome.ERROR, message=str(exc))

    # ── validação por tool ────────────────────────────────────────────────
    def _validate(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        args = args or {}
        if name in ("whatsapp.send_text",):
            return {
                "chat_id": validate_chat_id(args.get("recipient") or args.get("chat_id") or ""),
                "text": validate_text(args.get("text") or ""),
            }
        if name == "whatsapp.send_media":
            if not self.media_root:
                raise WhatsAppValidationError("media_root não configurado")
            return {
                "chat_id": validate_chat_id(args.get("recipient") or args.get("chat_id") or ""),
                "path": str(validate_media_path(args.get("path") or "", allowed_root=self.media_root)),
                "caption": validate_text(args.get("caption")) if args.get("caption") else "",
            }
        if name in ("whatsapp.get_chats", "whatsapp.get_messages"):
            if args.get("chat_id"):
                return {"chat_id": validate_chat_id(args["chat_id"])}
            return {}
        return {}

    def _execute(self, name: str, clean: Dict[str, Any]) -> ToolResult:
        if name == "whatsapp.status":
            st = self.provider.get_status()
            return ToolResult(ToolOutcome.OK, data=_status_dict(st))
        if name == "whatsapp.health":
            return ToolResult(ToolOutcome.OK, data={"healthy": self.provider.health_check()})
        if name == "whatsapp.sessions":
            st = self.provider.get_status()
            return ToolResult(ToolOutcome.OK, data={"sessions": [_status_dict(st)]})
        if name == "whatsapp.connect":
            self.provider.start()
            return ToolResult(ToolOutcome.OK, data=_status_dict(self.provider.get_status()))
        if name == "whatsapp.disconnect":
            self.provider.stop()
            return ToolResult(ToolOutcome.OK, data=_status_dict(self.provider.get_status()))
        if name == "whatsapp.send_text":
            res: SendResult = self.provider.send_text(clean["chat_id"], clean["text"])
            if res.ok:
                return ToolResult(ToolOutcome.OK, data={"message_id": res.message_id})
            return ToolResult(ToolOutcome.ERROR, message=res.error)
        # get_chats/get_messages/send_media dependem de métodos opcionais do
        # provider; se a impl não os declara em capabilities(), é indisponível.
        if name in ("whatsapp.get_chats", "whatsapp.get_messages", "whatsapp.send_media"):
            method = name.split(".", 1)[1]
            if method not in self.provider.capabilities():
                return ToolResult(ToolOutcome.SESSION_UNAVAILABLE, message=f"{method} não suportado por este provider")
            return ToolResult(ToolOutcome.ERROR, message=f"{method}: execução real device-required")
        return ToolResult(ToolOutcome.ERROR, message=f"tool não roteada: {name}")


def _status_dict(st: ProviderStatus) -> Dict[str, Any]:
    return {
        "provider": st.provider,
        "session_id": st.session_id,
        "state": st.state.value,
        "healthy": st.healthy,
        "detail": st.detail,
    }
