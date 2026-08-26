"""Eyes & Hands data contracts (Wave 2, §26-31).

Computer-Use, Browser and Visual-QA already exist as real integrations that drive
external binaries (cua-driver / agent-browser) and the Windows desktop app — their
REAL runtime is Windows-only (WAITING_FOR_HUMAN here). This module provides the
model-agnostic *contracts* + safety policy so IMPLEMENTATION/UNIT are testable on
Linux and a later runtime just fills them in. It does NOT create a ComputerUseV2 —
it is the typed surface the existing tools already speak.

Pure module: stdlib only; reuses the shared Decision enum.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from agent.autonomy_levels import Decision


# ============================ Computer Use ================================ #


class ComputerActionKind(str, Enum):
    OBSERVE = "observe"
    CAPTURE = "capture"
    LOCATE = "locate"
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    TYPE = "type"
    SCROLL = "scroll"
    KEY = "key"
    LIST_WINDOWS = "list_windows"
    FOCUS_WINDOW = "focus_window"
    LAUNCH_APP = "launch_app"
    OBSERVE_APP = "observe_app"


_MUTATING = frozenset({
    ComputerActionKind.CLICK, ComputerActionKind.DOUBLE_CLICK, ComputerActionKind.RIGHT_CLICK,
    ComputerActionKind.TYPE, ComputerActionKind.KEY, ComputerActionKind.SCROLL,
    ComputerActionKind.LAUNCH_APP, ComputerActionKind.FOCUS_WINDOW,
})

# dangerous key combos + type payloads that are blocked regardless of approval.
_BLOCKED_KEYS = frozenset({"ctrl-alt-del", "win-l", "meta-l", "alt-f4"})
_BLOCKED_TYPE = tuple(re.compile(p, re.IGNORECASE) for p in (
    r"curl\s+[^|]*\|\s*(?:bash|sh)", r"sudo\s+rm\s+-rf", r":\(\)\{.*\};:",
))


@dataclass(frozen=True)
class WindowTarget:
    app: str = ""
    pid: int | None = None
    window_id: str | None = None

    @property
    def is_exact(self) -> bool:
        return self.pid is not None and self.window_id is not None


@dataclass(frozen=True)
class SensitiveSurface:
    detected: bool = False
    reason: str = ""     # e.g. "password field", "banking app", "system settings"


@dataclass(frozen=True)
class ComputerAction:
    kind: ComputerActionKind
    target: WindowTarget = field(default_factory=WindowTarget)
    text: str = ""
    key: str = ""
    params: Mapping[str, object] = field(default_factory=dict)

    @property
    def mutating(self) -> bool:
        return self.kind in _MUTATING


@dataclass(frozen=True)
class Observation:
    screenshot_ref: str | None = None
    window: WindowTarget = field(default_factory=WindowTarget)
    element_count: int = 0
    sensitive: SensitiveSurface = field(default_factory=SensitiveSurface)


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    observation_after: Observation | None = None
    error: str | None = None


@dataclass(frozen=True)
class ComputerUsePolicy:
    """Capability gating for computer use (§28). Untrusted input never grants it."""

    allowed_apps: frozenset[str] = frozenset()   # empty == no allowlist restriction
    require_exact_target: bool = True

    def decide(self, action: ComputerAction, *, sensitive: SensitiveSurface | None = None) -> Decision:
        sensitive = sensitive or SensitiveSurface()
        # hard blocks first
        if action.kind == ComputerActionKind.KEY and action.key.lower() in _BLOCKED_KEYS:
            return Decision.DENY
        if action.kind == ComputerActionKind.TYPE and any(p.search(action.text) for p in _BLOCKED_TYPE):
            return Decision.DENY
        if not action.mutating:
            return Decision.ALLOW
        if self.allowed_apps and action.target.app and action.target.app not in self.allowed_apps:
            return Decision.DENY
        if self.require_exact_target and not action.target.is_exact:
            return Decision.HUMAN_GATE
        if sensitive.detected:
            return Decision.HUMAN_GATE     # sensitive surface -> human confirmation
        return Decision.ALLOW


# ================================ Browser ================================= #


@dataclass(frozen=True)
class ConsoleEvent:
    level: str      # log | warning | error
    text: str


@dataclass(frozen=True)
class NetworkEvent:
    method: str
    url: str
    status: int | None = None
    failed: bool = False


class BrowserActionKind(str, Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    UPLOAD = "upload"
    DOWNLOAD = "download"
    SNAPSHOT = "snapshot"       # a11y tree / DOM
    SCREENSHOT = "screenshot"
    CONSOLE = "console"
    NETWORK = "network"         # the gap the audit flagged (browser_network)
    SCROLL = "scroll"


@dataclass(frozen=True)
class BrowserAction:
    kind: BrowserActionKind
    ref: str = ""               # element ref from the latest snapshot (trusted only)
    url: str = ""
    text: str = ""


@dataclass(frozen=True)
class PageState:
    url: str = ""
    title: str = ""
    element_count: int = 0


@dataclass(frozen=True)
class BrowserObservation:
    page: PageState = field(default_factory=PageState)
    console: tuple[ConsoleEvent, ...] = ()
    network: tuple[NetworkEvent, ...] = ()
    screenshot_ref: str | None = None

    @property
    def console_errors(self) -> tuple[ConsoleEvent, ...]:
        return tuple(e for e in self.console if e.level == "error")

    @property
    def network_failures(self) -> tuple[NetworkEvent, ...]:
        return tuple(e for e in self.network if e.failed or (e.status or 0) >= 400)


# =============================== Visual QA =============================== #


class VisualFindingKind(str, Enum):
    OVERFLOW = "overflow"
    OVERLAP = "overlap"
    BROKEN_IMAGE = "broken_image"
    BAD_SPACING = "bad_spacing"
    LOW_CONTRAST = "low_contrast"
    FOCUS_INVISIBLE = "focus_invisible"
    RESPONSIVE_BUG = "responsive_bug"
    DEAD_CONTROL = "dead_control"
    CONSOLE_ERROR = "console_error"
    NETWORK_ERROR = "network_error"


@dataclass(frozen=True)
class ScreenshotEvidence:
    ref: str
    viewport: str            # e.g. "1280x800", "390x844"


@dataclass(frozen=True)
class VisualQaFinding:
    kind: VisualFindingKind
    severity: str = "medium"   # low | medium | high
    selector: str = ""
    viewport: str = ""
    detail: str = ""


@dataclass(frozen=True)
class VisualQaPolicy:
    """Which finding kinds block acceptance (§30)."""

    blocking: frozenset[VisualFindingKind] = frozenset({
        VisualFindingKind.OVERLAP, VisualFindingKind.BROKEN_IMAGE,
        VisualFindingKind.DEAD_CONTROL, VisualFindingKind.CONSOLE_ERROR,
        VisualFindingKind.NETWORK_ERROR,
    })

    def is_blocking(self, finding: VisualQaFinding) -> bool:
        return finding.kind in self.blocking or finding.severity == "high"


@dataclass(frozen=True)
class VisualQaRun:
    viewport: str
    findings: tuple[VisualQaFinding, ...] = ()
    before: ScreenshotEvidence | None = None
    after: ScreenshotEvidence | None = None

    def blocking(self, policy: VisualQaPolicy) -> tuple[VisualQaFinding, ...]:
        return tuple(f for f in self.findings if policy.is_blocking(f))

    def passed(self, policy: VisualQaPolicy) -> bool:
        return not self.blocking(policy)


@dataclass(frozen=True)
class VisualComparison:
    baseline_ref: str
    actual_ref: str
    diff_ref: str | None
    changed_ratio: float          # 0..1 fraction of pixels changed
    tolerance: float = 0.02       # ignore <=2% as noise

    @property
    def meaningful(self) -> bool:
        return self.changed_ratio > self.tolerance


__all__ = [
    "ComputerActionKind", "WindowTarget", "SensitiveSurface", "ComputerAction",
    "Observation", "ActionResult", "ComputerUsePolicy",
    "ConsoleEvent", "NetworkEvent", "BrowserActionKind", "BrowserAction",
    "PageState", "BrowserObservation",
    "VisualFindingKind", "ScreenshotEvidence", "VisualQaFinding", "VisualQaPolicy",
    "VisualQaRun", "VisualComparison",
]
