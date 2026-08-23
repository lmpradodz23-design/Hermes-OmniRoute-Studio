"""Capacidades do WhatsApp — mínimo privilégio, gate no ponto de execução.

Uma ferramenta MCP declara a capacidade que exige; o dispatcher recusa executar
sem ela. O renderer e o prompt do agente NÃO são a barreira — este gate é.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet


class WhatsAppCapability(str, Enum):
    READ = "whatsapp_read"          # status, sessions, get_chats, get_messages, health
    MANAGE = "whatsapp_manage"      # connect, disconnect, logout
    SEND = "whatsapp_send"          # send_text
    SEND_MEDIA = "whatsapp_send_media"  # send_media


class WhatsAppCapabilityDenied(Exception):
    pass


@dataclass
class WhatsAppGrants:
    """Concedidas para uma operação. Default = só leitura (mínimo privilégio).

    Enviar e gerenciar exigem concessão explícita — uma mensagem recebida
    NUNCA concede isso automaticamente."""

    granted: FrozenSet[WhatsAppCapability] = field(
        default_factory=lambda: frozenset({WhatsAppCapability.READ})
    )

    def require(self, capability: WhatsAppCapability) -> None:
        if capability not in self.granted:
            raise WhatsAppCapabilityDenied(f"capacidade não concedida: {capability.value}")

    def with_granted(self, *caps: WhatsAppCapability) -> "WhatsAppGrants":
        return WhatsAppGrants(granted=self.granted | set(caps))
