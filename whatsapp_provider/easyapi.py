"""Configuração do runtime externo do OpenWA (Easy API) — segura por padrão.

A auditoria achou que o Easy API do OpenWA sobe em 0.0.0.0? Não — o default é
`localhost`, mas a apiKey é OPCIONAL. Aqui a política é mais dura que o default
do upstream:

  * bind sempre em 127.0.0.1 (nunca 0.0.0.0);
  * apiKey OBRIGATÓRIA — mesmo em localhost, um processo local hostil não é
    confiável (§52);
  * a porta é validada/configurável, nunca hardcoded sem tratamento.

Este módulo NÃO faz rede — só monta e valida a configuração e o comando de
lançamento (argv), que o runtime do Hermes executa. Sem chamada HTTP aqui:
mantém o pacote testável e o segredo fora do log.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import List, Optional

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class EasyApiConfigError(Exception):
    pass


def generate_api_key() -> str:
    """Gera uma apiKey forte. Nunca reusa uma fixa, nunca vai para o Git."""
    return secrets.token_urlsafe(32)


@dataclass
class EasyApiConfig:
    """Config do runtime externo do OpenWA. apiKey obrigatória, bind loopback."""

    api_key: str
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    session_id: str = "session"
    session_data_path: str = ""   # fora do source control (ver .gitignore)

    def __post_init__(self) -> None:
        if not self.api_key or len(self.api_key) < 16:
            raise EasyApiConfigError("apiKey obrigatória (mín 16 chars) — localhost não é confiável")
        if self.host not in LOOPBACK_HOSTS:
            raise EasyApiConfigError(f"host precisa ser loopback, veio {self.host!r}")
        if not (1 <= self.port <= 65535):
            raise EasyApiConfigError(f"porta inválida: {self.port}")
        if not self.session_id.strip():
            raise EasyApiConfigError("session_id vazio")

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def launch_argv(self, *, npx: str = "npx") -> List[str]:
        """Monta o argv de lançamento do Easy API — por lista, nunca string de
        shell. `--api-key` via env no runtime real (não em argv) para não vazar
        em `ps`; aqui o placeholder marca onde ele entra."""
        return [
            npx,
            "--yes",
            "@open-wa/wa-automate@4.76.0",  # baseline estável (v4), não v5-alpha
            "--session", self.session_id,
            "--port", str(self.port),
            "--host", self.host,
            "--no-api-key-in-argv",  # sentinela: a key entra por env WA_API_KEY
        ]

    def env(self) -> dict:
        """Variáveis de ambiente para o processo. A apiKey vai AQUI, não no argv."""
        env = {"WA_API_KEY": self.api_key}
        if self.session_data_path:
            env["WA_SESSION_DATA_PATH"] = self.session_data_path
        return env


# Padrões redigidos em log (§54). QR, token, cookie, apiKey nunca em texto claro.
_REDACT_MARKERS = ("api_key", "apikey", "x-api-key", "token", "cookie", "qr", "session")


def redact_for_log(text: str) -> str:
    """Redige material sensível de uma linha de log. Conservador: se a linha
    menciona um marcador sensível seguido de um valor, o valor vira [REDACTED]."""
    import re

    # dataURL de QR PRIMEIRO (senão o redator de key-value corta só até a
    # vírgula e deixa o base64 exposto).
    out = re.sub(r"data:image/[a-z]+;base64,[A-Za-z0-9+/=]+", "data:image/[REDACTED]", text)
    # key=value / key: value / "key":"value"
    pattern = re.compile(
        r'(?i)("?(?:' + "|".join(re.escape(m) for m in _REDACT_MARKERS) + r')"?\s*[:=]\s*"?)([^\s",]+)'
    )
    out = pattern.sub(lambda m: m.group(1) + "[REDACTED]", out)
    return out
