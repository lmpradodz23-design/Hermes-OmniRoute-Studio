"""Real default injections for the provider layer (§ runtime wiring, stdlib-only).

These are the REAL implementations of the boundaries the pure layer injects — not
skeletons. They let the whole provider stack actually run (against real HTTP and the
real secret_sources registry), so a host only needs to render the UI and call in.

  - UrllibHttpClient: a working HttpClient over the standard library (no extra dep),
    turning HTTP errors into status codes the classifier understands.
  - SecretSourcesResolver: adapts the existing `agent/secret_sources` registry to the
    SecretResolver protocol (fetch a mapped env var's value).
  - default_service(): assembles a ProviderSettingsService bound to the REAL provider
    registry (`providers/`), a real secret store, and these injections.

Only the live network call and the OS keychain writer remain host-specific; everything
here is exercised by a real local-HTTP integration test (test_provider_runtime_integration).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Mapping

from agent.provider_catalog import ProviderCatalog
from agent.provider_secret_bridge import ProviderSecretStore
from agent.provider_settings_service import ProviderSettingsService


# ---- real HttpClient over stdlib urllib --------------------------------- #

@dataclass
class _Response:
    status_code: int
    _body: bytes = b""

    def json(self) -> object:
        if not self._body:
            return None
        return json.loads(self._body.decode("utf-8", "replace"))


class UrllibHttpClient:
    """A working HttpClient (agent.provider_probe.HttpClient) using only the stdlib.

    HTTP error responses (4xx/5xx) are returned as a _Response with that status code
    rather than raised, so provider_probe.classify_http_status handles them uniformly.
    Transport-level failures (DNS, refused, timeout) propagate and are classified as
    NETWORK_ERROR by health_check's exception guard.
    """

    def get(self, url: str, *, headers: Mapping[str, str] | None = None,
            timeout: float = 5.0) -> _Response:
        req = urllib.request.Request(url, headers=dict(headers or {}), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (trusted, provider base URLs)
                return _Response(getattr(r, "status", 200) or 200, r.read())
        except urllib.error.HTTPError as e:
            body = b""
            try:
                body = e.read()
            except Exception:
                pass
            return _Response(e.code, body)
        # urllib.error.URLError / socket.timeout propagate -> health_check -> NETWORK_ERROR


# ---- real SecretResolver over agent/secret_sources ---------------------- #

class SecretSourcesResolver:
    """Adapts the existing secret_sources registry to the SecretResolver protocol.

    `registry` is `agent.secret_sources.registry` (duck-typed: get_source / list_sources).
    `cfg_for` maps a source name to its config section; `home_path` is HERMES_HOME.
    A source's `fetch()` returns a FetchResult whose `.secrets` maps env var -> value,
    which is exactly what resolve_key() reads.
    """

    def __init__(self, registry, *, home_path, cfg_for=None):
        self._registry = registry
        self._home = home_path
        self._cfg_for = cfg_for or (lambda name: {})

    def fetch_env(self, env_var: str, source: str | None):
        sources = []
        if source is not None:
            s = self._registry.get_source(source)
            if s is not None:
                sources = [s]
        else:
            sources = list(self._registry.list_sources())
        for s in sources:
            res = s.fetch(self._cfg_for(getattr(s, "name", "")), self._home)
            if getattr(res, "ok", False) and env_var in dict(getattr(res, "secrets", {}) or {}):
                return res
        # nothing produced the var: synthesize a not-configured result the bridge understands
        return _EmptyFetch()


@dataclass
class _EmptyFetch:
    error: str = "not_configured"
    error_kind: object = None
    secrets: dict = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.secrets is None:
            object.__setattr__(self, "secrets", {})

    @property
    def ok(self) -> bool:
        return False


# ---- assembled default service ------------------------------------------ #

def default_service(*, registry=None, store: ProviderSecretStore | None = None,
                    catalog: ProviderCatalog | None = None) -> ProviderSettingsService:
    """Assemble a ProviderSettingsService bound to the REAL provider registry.

    `registry` defaults to the in-tree `providers/` module (lazy import so this module
    stays import-light). Pass a fake in tests.
    """
    if registry is None:
        import providers as registry  # the real OmniRoute provider registry
    return ProviderSettingsService(catalog or ProviderCatalog(),
                                   store or ProviderSecretStore(), registry)


def default_http_client() -> UrllibHttpClient:
    return UrllibHttpClient()


__all__ = [
    "UrllibHttpClient", "SecretSourcesResolver", "default_service", "default_http_client",
]
