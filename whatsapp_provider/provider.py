"""Contrato WhatsAppProvider — a interface que o Hermes conhece.

O core do Hermes fala SÓ com esta interface abstrata. O OpenWA fica atrás dela
(OpenWAProvider), e um futuro provider (Meta oficial, Evolution) entra sem
espalhar condicionais pela aplicação. É o que impede aprisionamento.

Nenhum método expõe tipo interno do OpenWA — só os contratos estáveis de
session.py / events.py / sending.py.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Callable, List, Optional

from .events import NormalizedEvent
from .session import SessionState


@dataclass(frozen=True)
class ProviderStatus:
    provider: str
    session_id: str
    state: SessionState
    healthy: bool
    detail: str = ""


@dataclass(frozen=True)
class SendResult:
    """Resultado de um envio. `message_id` só é preenchido em sucesso real."""

    ok: bool
    message_id: str = ""
    error: str = ""


class WhatsAppProvider(abc.ABC):
    """Contrato estável. Implementações: OpenWAProvider (v4/v5), futuros.

    `capabilities()` declara o que a implementação REALMENTE suporta — a UI usa
    isso para mostrar UNAVAILABLE em vez de um botão que falha. Nunca declarar
    capacidade não comprovada.
    """

    name: str = "abstract"

    @abc.abstractmethod
    def capabilities(self) -> frozenset[str]:
        """Conjunto de nomes de métodos realmente suportados por esta impl."""

    @abc.abstractmethod
    def start(self) -> None: ...

    @abc.abstractmethod
    def stop(self) -> None: ...

    @abc.abstractmethod
    def get_status(self) -> ProviderStatus: ...

    @abc.abstractmethod
    def health_check(self) -> bool: ...

    @abc.abstractmethod
    def send_text(self, chat_id: str, text: str) -> SendResult: ...

    @abc.abstractmethod
    def subscribe_events(self, handler: Callable[[NormalizedEvent], None]) -> None: ...


# Métodos do contrato usados pelos contract tests — um provider substituto tem
# que implementar todos.
REQUIRED_METHODS = frozenset({
    "capabilities", "start", "stop", "get_status", "health_check",
    "send_text", "subscribe_events",
})


def assert_conforms(provider_cls: type) -> List[str]:
    """Verifica que uma classe implementa o contrato. Devolve os faltantes.

    Base dos WhatsAppProviderContractTests: qualquer provider futuro roda contra
    isto, garantindo que substituir o OpenWA não exige tocar o core.
    """
    missing = []
    for method in REQUIRED_METHODS:
        attr = getattr(provider_cls, method, None)
        if attr is None or not callable(attr):
            missing.append(method)
        elif getattr(attr, "__isabstractmethod__", False):
            missing.append(method)
    return missing
