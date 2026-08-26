"""Settings -> AI & Models view-model (§4/§8/§10/§38 — the lay-user surface).

Builds the exact, secret-safe data the renderer needs to show a dead-simple
"AI & Models" screen: providers grouped into friendly sections, plain-language
badges (Recommended / Free / No card / Local & private / Connected), an official
"Get a key" link, and a guided connect flow (pick -> open key page -> paste ->
validate format -> test) that needs no JSON, terminal, or base-URL from the user.

HARD rules honored here:
  - No secret ever enters the view-model (keys live in OS secure storage; only a
    boolean `has_key` and connection status are surfaced). A defensive assert
    guarantees no secret-bearing field leaks.
  - Quotas/prices are never invented — a provider shows "Free tier available"
    only from the catalog's existence flag, never an amount.
  - Connection status is injected (real probes = runtime = WAITING_FOR_HUMAN);
    absent status renders as NOT_CONNECTED / UNKNOWN, never a fake CONNECTED.

Pure module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from agent.provider_adapter import (
    ConnectionStatus,
    local_health_url,
    user_message,
)
from agent.provider_catalog import (
    Curation,
    ProviderCatalog,
    ProviderEntry,
    Tri,
)

# Field names that would hold a raw secret VALUE (a leak). "key" alone is not a
# leak — has_key/needs_key/get_key_url are safe booleans/URLs — so we match on
# secret containers and treat only an unadorned `key`/`api_key` as forbidden.
_SECRET_VALUE_MARKERS = ("token", "secret", "password", "authorization", "credential")
_SAFE_KEY_FIELDS = frozenset({"has_key", "needs_key", "get_key_url"})


@dataclass(frozen=True)
class GuidedStep:
    order: int
    title: str
    detail: str
    href: str = ""          # official page for "open" steps; never a secret


@dataclass(frozen=True)
class ProviderCard:
    id: str
    name: str
    category: str
    badges: tuple[str, ...]
    capabilities: tuple[str, ...]
    connected: bool
    status: str
    status_message: str
    has_key: bool
    needs_key: bool
    get_key_url: str
    docs_link: str
    guided_steps: tuple[GuidedStep, ...]
    executable: bool

    def _assert_secret_safe(self) -> None:
        for fname in self.__dict__:
            low = fname.lower()
            if low in _SAFE_KEY_FIELDS:
                continue
            leaks = any(m in low for m in _SECRET_VALUE_MARKERS)
            leaks = leaks or low == "key" or low == "api_key"
            if leaks:
                raise AssertionError(f"secret-bearing field leaked into view: {fname}")


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    subtitle: str
    cards: tuple[ProviderCard, ...]


@dataclass(frozen=True)
class SettingsView:
    sections: tuple[Section, ...]
    quick_start_provider_id: str | None
    quick_start_reason: str
    local_only: bool = False

    def all_cards(self) -> tuple[ProviderCard, ...]:
        return tuple(c for s in self.sections for c in s.cards)


def _badges(e: ProviderEntry) -> tuple[str, ...]:
    out: list[str] = []
    if e.curation is Curation.RECOMMENDED:
        out.append("Recommended")
    if e.is_local:
        out.append("Local & private")
    if e.free_tier == Tri.YES:
        out.append("Free tier available")
    if e.no_card:
        out.append("No card needed")
    if e.curation is Curation.EXPERIMENTAL:
        out.append("Experimental")
    return tuple(out)


def _guided_steps(e: ProviderEntry) -> tuple[GuidedStep, ...]:
    if e.is_local:
        url = local_health_url(e.id) or e.api_base
        return (
            GuidedStep(1, "Install the local app", f"Install {e.name} and start it — runs on your machine, nothing leaves it."),
            GuidedStep(2, "Detect", "We check it's running locally.", href=url),
            GuidedStep(3, "Pick a model", "Choose any model you downloaded — no key, no account."),
        )
    steps = [
        GuidedStep(1, "Get a free key", f"Open {e.name}'s official key page and copy your key.", href=e.get_key_url),
        GuidedStep(2, "Paste it here", "Paste the key — we store it securely on your device, never in plain text."),
        GuidedStep(3, "Check the format", "We verify the key looks right before doing anything."),
        GuidedStep(4, "Test connection", "One click to confirm it works."),
    ]
    return tuple(steps)


def _card(e: ProviderEntry, *, has_key: bool,
          status: ConnectionStatus | None,
          executable: bool) -> ProviderCard:
    connected = status is ConnectionStatus.CONNECTED
    st = status or ConnectionStatus.UNKNOWN
    needs_key = not e.is_local
    card = ProviderCard(
        id=e.id,
        name=e.name,
        category=e.category.value,
        badges=_badges(e),
        capabilities=tuple(c.value for c in sorted(e.capabilities, key=lambda c: c.value)),
        connected=connected,
        status=st.value,
        status_message=(user_message(st) if status is not None
                        else ("Not connected yet." if needs_key else "Not detected yet.")),
        has_key=has_key,
        needs_key=needs_key,
        get_key_url=e.get_key_url,
        docs_link=e.docs_link,
        guided_steps=_guided_steps(e),
        executable=executable,
    )
    card._assert_secret_safe()
    return card


_SECTION_ORDER = (
    ("recommended", "Recommended", "The easiest ways to get started."),
    ("local", "Local & private", "Runs on your machine — nothing leaves your device."),
    ("free", "Free, no card", "Free tiers you can use without a credit card."),
    ("other", "More providers", "Additional providers and custom endpoints."),
)


def _section_for(e: ProviderEntry) -> str:
    if e.curation is Curation.RECOMMENDED and not e.is_local:
        return "recommended"
    if e.is_local:
        return "local"
    if e.free_tier == Tri.YES and e.no_card:
        return "free"
    return "other"


def build_settings_view(
    catalog: ProviderCatalog,
    *,
    configured: Mapping[str, bool] | None = None,       # provider_id -> has_key
    statuses: Mapping[str, ConnectionStatus] | None = None,
    executable: Mapping[str, bool] | None = None,       # from reconcile(): runtime profile exists
    local_only: bool = False,
) -> SettingsView:
    configured = configured or {}
    statuses = statuses or {}
    executable = executable or {}

    buckets: dict[str, list[ProviderCard]] = {k: [] for k, _, _ in _SECTION_ORDER}
    for e in catalog.all():
        # Under LOCAL_ONLY, cloud providers are shown but clearly ineligible.
        exec_ok = e.is_local if local_only else executable.get(e.id, e.is_local)
        card = _card(
            e,
            has_key=bool(configured.get(e.id, False)),
            status=statuses.get(e.id),
            executable=exec_ok,
        )
        buckets[_section_for(e)].append(card)

    sections = tuple(
        Section(key=k, title=title, subtitle=sub, cards=tuple(buckets[k]))
        for k, title, sub in _SECTION_ORDER if buckets[k]
    )

    qs_id, qs_reason = _quick_start(catalog, statuses, local_only)
    return SettingsView(sections=sections, quick_start_provider_id=qs_id,
                        quick_start_reason=qs_reason, local_only=local_only)


def _quick_start(catalog: ProviderCatalog, statuses: Mapping[str, ConnectionStatus],
                 local_only: bool) -> tuple[str | None, str]:
    # Prefer a local provider that's already detected/connected.
    for e in catalog.filter(local=True):
        if statuses.get(e.id) is ConnectionStatus.CONNECTED:
            return e.id, "A local model is already running — fully private and free."
    if local_only:
        locals_ = catalog.filter(local=True)
        if locals_:
            return locals_[0].id, "Local-only mode: install a local model to keep everything on-device."
        return None, "Local-only mode is on but no local provider is available."
    # Else the easiest free, no-card, recommended cloud option.
    for e in catalog.recommended():
        if not e.is_local and e.free_tier == Tri.YES and e.no_card:
            return e.id, "Free tier and no credit card — quickest way to start."
    locals_ = catalog.filter(local=True)
    if locals_:
        return locals_[0].id, "Install a local model for a free, private default."
    return None, "Pick any provider and add a key to begin."


__all__ = ["GuidedStep", "ProviderCard", "Section", "SettingsView", "build_settings_view"]
