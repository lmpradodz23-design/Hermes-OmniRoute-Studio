"""Cliente do Easy API do OpenWA — auth local Hermes↔runtime, testável sem rede.

O Hermes fala com o runtime externo do OpenWA (Easy API em 127.0.0.1) por HTTP
autenticado. Este módulo monta a requisição autenticada e roteia a resposta, com
o transporte INJETADO — nenhuma chamada de rede acontece aqui, então é testável e
o segredo nunca sai do processo em log/argv/URL.

Disciplina da apiKey (§52/§54):
  * a key vai SÓ no header `X-API-Key` — nunca na URL, nunca no corpo, nunca em
    log; `redacted()` e `__repr__` mascaram;
  * a URL é sempre o base_url loopback da config — path vem de uma ALLOWLIST de
    endpoints, nunca de entrada não confiável (um chat_id jamais vira path);
  * o transporte é injetado: `EasyApiClient(config, transport)`. Em produção o
    runtime passa um transporte HTTP real; nos testes, um fake.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from .easyapi import EasyApiConfig
from .validation import validate_chat_id, validate_text


API_KEY_HEADER = "X-API-Key"

# Endpoints do Easy API que o Hermes pode chamar. Path nunca vem de fora disto.
ENDPOINT_ALLOWLIST = frozenset({
    "getConnectionState",
    "getHostDevice",
    "sendText",
})


class EasyApiClientError(Exception):
    pass


@dataclass
class EasyApiRequest:
    method: str
    url: str
    headers: Dict[str, str]
    json: Optional[Dict[str, Any]] = None

    def redacted(self) -> Dict[str, Any]:
        """Versão para log: mascara o valor do header de auth."""
        safe_headers = dict(self.headers)
        if API_KEY_HEADER in safe_headers:
            safe_headers[API_KEY_HEADER] = "[REDACTED]"
        return {"method": self.method, "url": self.url, "headers": safe_headers, "json": self.json}

    def __repr__(self) -> str:  # nunca vaza a key num traceback/log
        return f"EasyApiRequest(method={self.method!r}, url={self.url!r}, headers=<redacted>)"


@dataclass
class EasyApiResponse:
    status: int
    body: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


Transport = Callable[[EasyApiRequest], EasyApiResponse]


class EasyApiClient:
    def __init__(self, config: EasyApiConfig, transport: Transport):
        self._config = config
        self._transport = transport

    # ── construção da requisição ──────────────────────────────────────────
    def build(self, endpoint: str, *, method: str = "POST", args: Optional[Dict[str, Any]] = None) -> EasyApiRequest:
        if endpoint not in ENDPOINT_ALLOWLIST:
            raise EasyApiClientError(f"endpoint fora da allowlist: {endpoint!r}")
        url = f"{self._config.base_url}/{endpoint}"
        body = {"args": args} if args is not None else None
        return EasyApiRequest(method=method, url=url, headers=self._auth_headers(), json=body)

    def _auth_headers(self) -> Dict[str, str]:
        # a key entra SÓ aqui, no header.
        return {API_KEY_HEADER: self._config.api_key, "Content-Type": "application/json"}

    # ── chamadas de alto nível ────────────────────────────────────────────
    def get_connection_state(self) -> EasyApiResponse:
        return self._transport(self.build("getConnectionState", method="GET"))

    def send_text(self, chat_id: str, text: str) -> EasyApiResponse:
        # valida ANTES de montar — chat_id/text hostis não passam.
        clean_chat = validate_chat_id(chat_id)
        clean_text = validate_text(text)
        req = self.build("sendText", args={"to": clean_chat, "content": clean_text})
        return self._transport(req)

    def __repr__(self) -> str:  # o cliente também nunca imprime a key
        return f"EasyApiClient(base_url={self._config.base_url!r})"
