"""OmniRoute Provider Catalog (§2/§20/§35).

A structured catalog of model providers that EXTENDS OmniRoute (it is metadata +
selection input, not a parallel router). Capability flags are stable public facts;
anything that would require live verification (quotas, prices) is UNKNOWN — this
module never invents quotas. Curation marks RECOMMENDED/SUPPORTED/EXPERIMENTAL/
DEPRECATED. Pure data module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class Category(str, Enum):
    CLOUD = "cloud"
    LOCAL = "local"
    AGGREGATOR = "aggregator"
    COMPATIBLE = "openai_compatible"


class AuthType(str, Enum):
    API_KEY = "api_key"
    NONE = "none"          # local, no key
    CUSTOM = "custom"


class Tri(str, Enum):
    YES = "YES"
    NO = "NO"
    UNKNOWN = "UNKNOWN"


class Privacy(str, Enum):
    LOCAL = "LOCAL"        # runs on device, no egress
    CLOUD = "CLOUD"        # data leaves the machine
    UNKNOWN = "UNKNOWN"


class Curation(str, Enum):
    RECOMMENDED = "RECOMMENDED"
    SUPPORTED = "SUPPORTED"
    EXPERIMENTAL = "EXPERIMENTAL"
    DEPRECATED = "DEPRECATED"


class Capability(str, Enum):
    CHAT = "CHAT"
    CODING = "CODING"
    VISION = "VISION"
    IMAGE = "IMAGE"
    EMBEDDING = "EMBEDDING"
    AUDIO = "AUDIO"
    TOOLS = "TOOLS"
    STRUCTURED_OUTPUT = "STRUCTURED_OUTPUT"
    LONG_CONTEXT = "LONG_CONTEXT"


@dataclass(frozen=True)
class ProviderEntry:
    id: str
    name: str
    category: Category
    capabilities: frozenset[Capability]
    auth_type: AuthType = AuthType.API_KEY
    privacy: Privacy = Privacy.CLOUD
    free_tier: Tri = Tri.UNKNOWN          # existence of a free tier (NOT a quota)
    requires_card: Tri = Tri.UNKNOWN
    supports_openai_compat: bool = False
    supports_local: bool = False
    curation: Curation = Curation.SUPPORTED
    api_base: str = ""
    get_key_url: str = ""                 # official page to obtain a key (§8)
    docs_link: str = ""
    # Verifiable-only fields — left empty/UNKNOWN unless verified live:
    free_tier_notes: str = ""
    pricing_link: str = ""
    last_verified_at: float | None = None

    @property
    def is_local(self) -> bool:
        return self.category == Category.LOCAL or self.privacy == Privacy.LOCAL

    @property
    def no_card(self) -> bool:
        return self.requires_card == Tri.NO or self.is_local

    def has(self, cap: Capability) -> bool:
        return cap in self.capabilities


def _c(*caps: Capability) -> frozenset[Capability]:
    return frozenset(caps)


_CHAT_CODE_TOOLS = _c(Capability.CHAT, Capability.CODING, Capability.TOOLS,
                      Capability.STRUCTURED_OUTPUT)


# Curated entries. Cloud providers = CLOUD privacy; local = LOCAL, no key, free.
# free_tier=YES only marks that a free tier/model publicly exists (no quota numbers).
_ENTRIES: tuple[ProviderEntry, ...] = (
    ProviderEntry("openai", "OpenAI", Category.CLOUD,
                  _CHAT_CODE_TOOLS | _c(Capability.VISION, Capability.IMAGE, Capability.EMBEDDING, Capability.AUDIO, Capability.LONG_CONTEXT),
                  privacy=Privacy.CLOUD, free_tier=Tri.NO, requires_card=Tri.YES,
                  supports_openai_compat=True, curation=Curation.RECOMMENDED,
                  api_base="https://api.openai.com/v1", get_key_url="https://platform.openai.com/api-keys",
                  docs_link="https://platform.openai.com/docs"),
    ProviderEntry("anthropic", "Anthropic / Claude", Category.CLOUD,
                  _CHAT_CODE_TOOLS | _c(Capability.VISION, Capability.LONG_CONTEXT),
                  free_tier=Tri.UNKNOWN, requires_card=Tri.YES, curation=Curation.RECOMMENDED,
                  api_base="https://api.anthropic.com", get_key_url="https://console.anthropic.com/settings/keys",
                  docs_link="https://docs.anthropic.com"),
    ProviderEntry("gemini", "Google Gemini", Category.CLOUD,
                  _CHAT_CODE_TOOLS | _c(Capability.VISION, Capability.IMAGE, Capability.EMBEDDING, Capability.LONG_CONTEXT),
                  free_tier=Tri.YES, requires_card=Tri.NO, curation=Curation.RECOMMENDED,
                  api_base="https://generativelanguage.googleapis.com", get_key_url="https://aistudio.google.com/apikey",
                  docs_link="https://ai.google.dev/docs"),
    ProviderEntry("openrouter", "OpenRouter", Category.AGGREGATOR,
                  _CHAT_CODE_TOOLS | _c(Capability.VISION, Capability.LONG_CONTEXT),
                  free_tier=Tri.YES, requires_card=Tri.NO, supports_openai_compat=True,
                  curation=Curation.RECOMMENDED, api_base="https://openrouter.ai/api/v1",
                  get_key_url="https://openrouter.ai/keys", docs_link="https://openrouter.ai/docs"),
    ProviderEntry("groq", "Groq", Category.CLOUD, _CHAT_CODE_TOOLS,
                  free_tier=Tri.YES, requires_card=Tri.NO, supports_openai_compat=True,
                  curation=Curation.RECOMMENDED, api_base="https://api.groq.com/openai/v1",
                  get_key_url="https://console.groq.com/keys", docs_link="https://console.groq.com/docs"),
    ProviderEntry("mistral", "Mistral", Category.CLOUD,
                  _CHAT_CODE_TOOLS | _c(Capability.EMBEDDING),
                  free_tier=Tri.YES, requires_card=Tri.UNKNOWN, supports_openai_compat=True,
                  api_base="https://api.mistral.ai/v1", get_key_url="https://console.mistral.ai/api-keys",
                  docs_link="https://docs.mistral.ai"),
    ProviderEntry("xiaomi-mimo", "Xiaomi MiMo", Category.CLOUD, _c(Capability.CHAT, Capability.CODING),
                  free_tier=Tri.UNKNOWN, curation=Curation.EXPERIMENTAL,
                  docs_link=""),
    ProviderEntry("cerebras", "Cerebras", Category.CLOUD, _CHAT_CODE_TOOLS,
                  free_tier=Tri.YES, requires_card=Tri.NO, supports_openai_compat=True,
                  api_base="https://api.cerebras.ai/v1", get_key_url="https://cloud.cerebras.ai",
                  docs_link="https://inference-docs.cerebras.ai"),
    ProviderEntry("together", "Together", Category.CLOUD,
                  _CHAT_CODE_TOOLS | _c(Capability.IMAGE, Capability.EMBEDDING),
                  free_tier=Tri.UNKNOWN, supports_openai_compat=True,
                  api_base="https://api.together.xyz/v1", get_key_url="https://api.together.ai/settings/api-keys",
                  docs_link="https://docs.together.ai"),
    ProviderEntry("fireworks", "Fireworks", Category.CLOUD,
                  _CHAT_CODE_TOOLS | _c(Capability.IMAGE),
                  free_tier=Tri.UNKNOWN, supports_openai_compat=True,
                  api_base="https://api.fireworks.ai/inference/v1", get_key_url="https://fireworks.ai/api-keys",
                  docs_link="https://docs.fireworks.ai"),
    ProviderEntry("deepseek", "DeepSeek", Category.CLOUD, _CHAT_CODE_TOOLS,
                  free_tier=Tri.UNKNOWN, requires_card=Tri.UNKNOWN, supports_openai_compat=True,
                  api_base="https://api.deepseek.com", get_key_url="https://platform.deepseek.com/api_keys",
                  docs_link="https://api-docs.deepseek.com"),
    # ---- local (free, no key, maximum privacy) ---- #
    ProviderEntry("ollama", "Ollama (Local)", Category.LOCAL,
                  _CHAT_CODE_TOOLS | _c(Capability.VISION, Capability.EMBEDDING),
                  auth_type=AuthType.NONE, privacy=Privacy.LOCAL, free_tier=Tri.YES,
                  requires_card=Tri.NO, supports_openai_compat=True, supports_local=True,
                  curation=Curation.RECOMMENDED, api_base="http://127.0.0.1:11434",
                  docs_link="https://ollama.com"),
    ProviderEntry("lmstudio", "LM Studio (Local)", Category.LOCAL, _CHAT_CODE_TOOLS,
                  auth_type=AuthType.NONE, privacy=Privacy.LOCAL, free_tier=Tri.YES,
                  requires_card=Tri.NO, supports_openai_compat=True, supports_local=True,
                  api_base="http://127.0.0.1:1234/v1", docs_link="https://lmstudio.ai"),
    ProviderEntry("vllm", "vLLM (Local)", Category.LOCAL, _CHAT_CODE_TOOLS,
                  auth_type=AuthType.NONE, privacy=Privacy.LOCAL, free_tier=Tri.YES,
                  requires_card=Tri.NO, supports_openai_compat=True, supports_local=True,
                  curation=Curation.SUPPORTED, api_base="http://127.0.0.1:8000/v1",
                  docs_link="https://docs.vllm.ai"),
    ProviderEntry("llamacpp", "llama.cpp (Local)", Category.LOCAL, _c(Capability.CHAT, Capability.CODING),
                  auth_type=AuthType.NONE, privacy=Privacy.LOCAL, free_tier=Tri.YES,
                  requires_card=Tri.NO, supports_openai_compat=True, supports_local=True,
                  api_base="http://127.0.0.1:8080/v1", docs_link="https://github.com/ggml-org/llama.cpp"),
    ProviderEntry("openai-compatible", "OpenAI-compatible (Custom)", Category.COMPATIBLE,
                  _c(Capability.CHAT), auth_type=AuthType.CUSTOM, privacy=Privacy.UNKNOWN,
                  free_tier=Tri.UNKNOWN, supports_openai_compat=True, curation=Curation.EXPERIMENTAL),
)


class ProviderCatalog:
    def __init__(self, entries: Iterable[ProviderEntry] = _ENTRIES):
        self._by_id = {e.id: e for e in entries}

    def all(self) -> tuple[ProviderEntry, ...]:
        return tuple(self._by_id.values())

    def get(self, provider_id: str) -> ProviderEntry | None:
        return self._by_id.get(provider_id)

    def by_capability(self, cap: Capability) -> tuple[ProviderEntry, ...]:
        return tuple(e for e in self._by_id.values() if e.has(cap))

    def filter(self, *, free: bool | None = None, local: bool | None = None,
               no_card: bool | None = None, capability: Capability | None = None,
               curation: Curation | None = None) -> tuple[ProviderEntry, ...]:
        out = list(self._by_id.values())
        if free is not None:
            out = [e for e in out if (e.free_tier == Tri.YES) == free]
        if local is not None:
            out = [e for e in out if e.is_local == local]
        if no_card is not None:
            out = [e for e in out if e.no_card == no_card]
        if capability is not None:
            out = [e for e in out if e.has(capability)]
        if curation is not None:
            out = [e for e in out if e.curation == curation]
        return tuple(out)

    def search(self, query: str) -> tuple[ProviderEntry, ...]:
        q = query.lower().strip()
        return tuple(e for e in self._by_id.values()
                     if q in e.id.lower() or q in e.name.lower())

    def recommended(self) -> tuple[ProviderEntry, ...]:
        return self.filter(curation=Curation.RECOMMENDED)


__all__ = [
    "Category", "AuthType", "Tri", "Privacy", "Curation", "Capability",
    "ProviderEntry", "ProviderCatalog",
]
