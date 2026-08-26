# OmniRoute Provider Catalog

> Auto-generated from `agent/provider_catalog.py` (the single source of truth). This is **metadata for provider selection and the Settings → AI & Models UI** — it extends OmniRoute, it is not a second router. Runtime execution still goes through the existing `providers/` registry (`ProviderProfile`).

## Honesty rules

- **Quotas and prices are never invented.** A provider is marked *Free tier: Yes* only when a free tier/model publicly exists — **not** any specific amount, request count, or token limit. Actual limits are **Unknown** until verified live at the provider.
- **Capabilities** are stable public facts (e.g. vision support). If a runtime profile contradicts the catalog, reconciliation **flags the drift** rather than asserting either as truth.
- **Privacy:** `Local` providers run on your machine (no egress). Under **LOCAL_ONLY** mode, cloud providers are **ineligible even if free**.
- **Secrets** are stored in OS-backed secure storage; the UI and logs only ever see `[stored securely]`, never a raw key.


## Recommended (cloud)

| Provider | Capabilities | Free tier | Card required | Privacy | OpenAI-compatible | Get a key |
|---|---|---|---|---|---|---|
| **OpenAI** (`openai`) | Chat, Coding, Vision, Image, Embedding, Audio, Tools, Structured Output, Long Context | No | Yes | Cloud | Yes | [key](https://platform.openai.com/api-keys) |
| **Anthropic / Claude** (`anthropic`) | Chat, Coding, Vision, Tools, Structured Output, Long Context | Unknown | Yes | Cloud | No | [key](https://console.anthropic.com/settings/keys) |
| **Google Gemini** (`gemini`) | Chat, Coding, Vision, Image, Embedding, Tools, Structured Output, Long Context | Yes | No | Cloud | No | [key](https://aistudio.google.com/apikey) |
| **OpenRouter** (`openrouter`) | Chat, Coding, Vision, Tools, Structured Output, Long Context | Yes | No | Cloud | Yes | [key](https://openrouter.ai/keys) |
| **Groq** (`groq`) | Chat, Coding, Tools, Structured Output | Yes | No | Cloud | Yes | [key](https://console.groq.com/keys) |

## Local & private (no key, no card, maximum privacy)

| Provider | Capabilities | Free tier | Card required | Privacy | OpenAI-compatible | Get a key |
|---|---|---|---|---|---|---|
| **Ollama (Local)** (`ollama`) | Chat, Coding, Vision, Embedding, Tools, Structured Output | Yes | No key needed | Local (on-device) | Yes | — |
| **LM Studio (Local)** (`lmstudio`) | Chat, Coding, Tools, Structured Output | Yes | No key needed | Local (on-device) | Yes | — |
| **vLLM (Local)** (`vllm`) | Chat, Coding, Tools, Structured Output | Yes | No key needed | Local (on-device) | Yes | — |
| **llama.cpp (Local)** (`llamacpp`) | Chat, Coding | Yes | No key needed | Local (on-device) | Yes | — |

## More providers

| Provider | Capabilities | Free tier | Card required | Privacy | OpenAI-compatible | Get a key |
|---|---|---|---|---|---|---|
| **Mistral** (`mistral`) | Chat, Coding, Embedding, Tools, Structured Output | Yes | Unknown | Cloud | Yes | [key](https://console.mistral.ai/api-keys) |
| **Xiaomi MiMo** (`xiaomi-mimo`) | Chat, Coding | Unknown | Unknown | Cloud | No | — |
| **Cerebras** (`cerebras`) | Chat, Coding, Tools, Structured Output | Yes | No | Cloud | Yes | [key](https://cloud.cerebras.ai) |
| **Together** (`together`) | Chat, Coding, Image, Embedding, Tools, Structured Output | Unknown | Unknown | Cloud | Yes | [key](https://api.together.ai/settings/api-keys) |
| **Fireworks** (`fireworks`) | Chat, Coding, Image, Tools, Structured Output | Unknown | Unknown | Cloud | Yes | [key](https://fireworks.ai/api-keys) |
| **DeepSeek** (`deepseek`) | Chat, Coding, Tools, Structured Output | Unknown | Unknown | Cloud | Yes | [key](https://platform.deepseek.com/api_keys) |
| **OpenAI-compatible (Custom)** (`openai-compatible`) | Chat | Unknown | Unknown | Unknown | Yes | — |

## Legend

- **Free tier = Yes**: a free tier/model exists (amount **Unknown** — verify at the provider).
- **Card required = Unknown**: not verified; check the provider's signup.
- **OpenAI-compatible**: can be driven through an OpenAI-style `/v1` endpoint.


_Last generated from source; no field here was hand-entered._

