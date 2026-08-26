"""Provider health-check + model-discovery + local-detection contracts (§5/§6/§13).

All network I/O is injected via the `HttpClient` protocol, so the CLASSIFICATION and
PARSING logic here is 100% pure and unit-testable with no real network. The real
HttpClient (requests/httpx) is wired at runtime on the app host (= WAITING_FOR_HUMAN);
nothing here performs a live call by itself.

Classification maps transport outcomes to the ConnectionStatus vocabulary the UI shows.
Model discovery parses both the OpenAI shape (`{"data":[{"id":...}]}`) and the Ollama
shape (`{"models":[{"name":...}]}`). Local detection probes only 127.0.0.1 endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence

from agent.provider_adapter import ConnectionStatus, local_health_url


# ---- injected transport (real one = requests/httpx at runtime) ---------- #

class HttpResponse(Protocol):
    status_code: int
    def json(self) -> object: ...


class HttpClient(Protocol):
    def get(self, url: str, *, headers: Mapping[str, str] | None = None,
            timeout: float = 5.0) -> HttpResponse: ...


# ---- classification (pure) ---------------------------------------------- #

def classify_http_status(code: int) -> ConnectionStatus:
    if 200 <= code < 300:
        return ConnectionStatus.CONNECTED
    if code in (401, 403):
        return ConnectionStatus.INVALID_KEY
    if code == 402:
        return ConnectionStatus.NO_QUOTA
    if code == 429:
        return ConnectionStatus.RATE_LIMITED
    if 500 <= code < 600:
        return ConnectionStatus.PROVIDER_DOWN
    if code == 404:
        return ConnectionStatus.CONFIG_ERROR      # wrong base URL / endpoint
    return ConnectionStatus.UNKNOWN


_NETWORK_EXC_MARKERS = ("timeout", "timed out", "connection", "refused",
                        "unreachable", "name resolution", "getaddrinfo", "ssl")


def classify_exception(exc: BaseException) -> ConnectionStatus:
    text = f"{type(exc).__name__} {exc}".lower()
    if any(m in text for m in _NETWORK_EXC_MARKERS):
        return ConnectionStatus.NETWORK_ERROR
    return ConnectionStatus.UNKNOWN


# ---- results ------------------------------------------------------------ #

@dataclass(frozen=True)
class ProbeResult:
    provider_id: str
    status: ConnectionStatus
    detail: str = ""
    models: tuple[str, ...] = field(default_factory=tuple)


# ---- model discovery (pure parsing) ------------------------------------- #

def _models_url(api_base: str, provider_id: str) -> str:
    base = (api_base or "").rstrip("/")
    if provider_id == "ollama":
        # ollama native tags endpoint (base has no /v1)
        root = base[:-3] if base.endswith("/v1") else base
        return f"{root}/api/tags"
    return f"{base}/models"


def parse_models(payload: object, provider_id: str = "") -> list[str]:
    """Parse an OpenAI-style or Ollama-style models payload into a list of ids."""
    if not isinstance(payload, Mapping):
        return []
    out: list[str] = []
    data = payload.get("data")
    if isinstance(data, Sequence) and not isinstance(data, (str, bytes)):
        for m in data:
            if isinstance(m, Mapping) and m.get("id"):
                out.append(str(m["id"]))
    models = payload.get("models")
    if isinstance(models, Sequence) and not isinstance(models, (str, bytes)):
        for m in models:
            if isinstance(m, Mapping):
                name = m.get("name") or m.get("id") or m.get("model")
                if name:
                    out.append(str(name))
    # de-dup, preserve order
    seen: set[str] = set()
    return [x for x in out if not (x in seen or seen.add(x))]


# ---- health check + discovery (I/O injected) ---------------------------- #

def health_check(
    provider_id: str,
    api_base: str,
    *,
    http: HttpClient,
    key: str | None = None,
    is_local: bool = False,
    timeout: float = 5.0,
) -> ProbeResult:
    """Probe a provider's models endpoint and classify. Never raises."""
    url = _models_url(api_base, provider_id) if not is_local else (
        local_health_url(provider_id) or _models_url(api_base, provider_id))
    headers = {}
    if key and not is_local:
        headers["Authorization"] = f"Bearer {key}"
    try:
        resp = http.get(url, headers=headers, timeout=timeout)
    except BaseException as exc:                      # noqa: BLE001 - fail safe to a status
        return ProbeResult(provider_id, classify_exception(exc), detail="probe_exception")
    status = classify_http_status(getattr(resp, "status_code", 0))
    models: tuple[str, ...] = ()
    if status is ConnectionStatus.CONNECTED:
        try:
            models = tuple(parse_models(resp.json(), provider_id))
        except BaseException:                        # noqa: BLE001 - discovery is best-effort
            models = ()
    return ProbeResult(provider_id, status, detail=url, models=models)


def discover_models(provider_id: str, api_base: str, *, http: HttpClient,
                    key: str | None = None, is_local: bool = False,
                    timeout: float = 5.0) -> list[str]:
    return list(health_check(provider_id, api_base, http=http, key=key,
                             is_local=is_local, timeout=timeout).models)


# ---- local auto-detection (127.0.0.1 only) ------------------------------ #

_LOCAL_IDS = ("ollama", "lmstudio", "vllm", "llamacpp")


def detect_local(provider_id: str, *, http: HttpClient, timeout: float = 2.0) -> ProbeResult:
    """Detect a local provider by probing its localhost health URL. Never raises."""
    url = local_health_url(provider_id)
    if not url:
        return ProbeResult(provider_id, ConnectionStatus.CONFIG_ERROR, detail="no_local_url")
    try:
        resp = http.get(url, timeout=timeout)
    except BaseException as exc:                      # noqa: BLE001
        # a local provider that's simply not running reads as PROVIDER_DOWN, not a hard error
        st = classify_exception(exc)
        return ProbeResult(provider_id,
                           ConnectionStatus.PROVIDER_DOWN if st is ConnectionStatus.NETWORK_ERROR else st,
                           detail="not_running")
    status = classify_http_status(getattr(resp, "status_code", 0))
    models: tuple[str, ...] = ()
    if status is ConnectionStatus.CONNECTED:
        try:
            models = tuple(parse_models(resp.json(), provider_id))
        except BaseException:                        # noqa: BLE001
            models = ()
    return ProbeResult(provider_id, status, detail=url, models=models)


def detect_all_local(*, http: HttpClient, timeout: float = 2.0) -> dict[str, ProbeResult]:
    return {pid: detect_local(pid, http=http, timeout=timeout) for pid in _LOCAL_IDS}


__all__ = [
    "HttpClient", "HttpResponse", "ProbeResult",
    "classify_http_status", "classify_exception", "parse_models",
    "health_check", "discover_models", "detect_local", "detect_all_local",
]
