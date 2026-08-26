"""Capability Acquisition Engine (§141-165).

Rule: MISSING_CAPABILITY != MISSION_BLOCKED. When a mission node needs a tool /
runtime / package / skill / provider that can be acquired SAFELY, the kernel
should DETECT -> DISCOVER -> EVALUATE -> ACQUIRE (in isolation, transactionally)
-> VERIFY -> REGISTER -> RESUME the original node, instead of stopping and asking
the user. It stops for a human ONLY on a real gate (privilege / cost / external
credential / hardware / platform / legal) or a security hard-stop.

This module is the pure, testable core: detection, risk classification, the
security hard-stop, the acquire transaction (checkpoint->install->verify->smoke
->promote, with rollback), the capability registry, and the Mission-DAG dynamic
ACQUIRE node. Actual installs are performed by injected callables (sandboxed in
real runtime; fakes in tests) — this module never runs an installer itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Callable, Iterable, Mapping, Sequence

from agent.mission_dag import DagNode, MissionDag


class AcquisitionRisk(str, Enum):
    LOW_RISK = "LOW_RISK"        # project-local dep / venv package -> auto
    MEDIUM_RISK = "MEDIUM_RISK"  # browser binary / docker image / sys package -> sandbox/policy
    HIGH_RISK = "HIGH_RISK"      # admin/root / driver / firewall / prod mutation -> HUMAN_GATE
    EXTERNAL = "EXTERNAL"        # credential / hardware / platform / legal -> BLOCKED_BY_EXTERNAL


class AcquisitionDecision(str, Enum):
    ACQUIRE = "ACQUIRE"
    HUMAN_GATE = "HUMAN_GATE"
    BLOCKED_BY_EXTERNAL_DEPENDENCY = "BLOCKED_BY_EXTERNAL_DEPENDENCY"
    FORBIDDEN = "FORBIDDEN"      # security hard-stop


class AcquisitionState(str, Enum):
    REGISTERED = "REGISTERED"        # acquired + verified + registered (capability ready)
    HUMAN_GATE = "HUMAN_GATE"
    BLOCKED_BY_EXTERNAL_DEPENDENCY = "BLOCKED_BY_EXTERNAL_DEPENDENCY"
    FORBIDDEN = "FORBIDDEN"
    FAILED = "FAILED"                # all safe candidates failed install/verify/smoke


# Missing-capability signals that must trigger acquisition, not final failure (§156).
_MISSING_PATTERNS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"command not found",
        r"not found on \$?PATH",
        r"ModuleNotFoundError",
        r"No module named",
        r"executable doesn'?t exist",
        r"browser (?:executable|binary) (?:missing|not found)",
        r"please run .*install",
        r"toolchain (?:missing|not found)",
        r"is not installed",
    )
)


def looks_like_missing_capability(reason: str) -> bool:
    return any(p.search(reason or "") for p in _MISSING_PATTERNS)


def classify_block(reason: str) -> str:
    """Watchdog helper (§160): distinguish a missing capability from a stuck task."""
    return "MISSING_CAPABILITY" if looks_like_missing_capability(reason) else "TASK_STUCK"


@dataclass(frozen=True)
class Candidate:
    """A discovered way to acquire a capability, plus its safety attributes."""

    name: str
    version: str = ""
    source: str = ""                    # registry / official repo / package manager ...
    risk: AcquisitionRisk = AcquisitionRisk.LOW_RISK
    license: str = ""
    signed: bool = True
    from_arbitrary_url: bool = False    # not an official/verifiable source
    known_malicious: bool = False
    requires_credential: bool = False   # e.g. a credential-stealing tool, or needs a secret
    has_cost: bool = False
    requires_privilege: bool = False    # admin/root


@dataclass(frozen=True)
class Capability:
    """A registered, acquired capability (§148)."""

    id: str
    version: str
    source: str
    platform: str
    install_scope: str          # project | venv | container | sandbox | system
    permissions: tuple[str, ...] = ()
    health: str = "ok"
    verification: str = ""      # what proved it works (smoke ref)
    risk: AcquisitionRisk = AcquisitionRisk.LOW_RISK
    license: str = ""


class CapabilityRegistry:
    def __init__(self) -> None:
        self._caps: dict[str, Capability] = {}

    def register(self, cap: Capability) -> None:
        self._caps[cap.id] = cap

    def has(self, cap_id: str) -> bool:
        return cap_id in self._caps

    def get(self, cap_id: str) -> Capability | None:
        return self._caps.get(cap_id)

    def ids(self) -> tuple[str, ...]:
        return tuple(self._caps)


# ---- security hard-stop (§163) ------------------------------------------- #


def is_forbidden(candidate: Candidate) -> bool:
    """Security gate that prevails over autonomy — never auto-acquire these."""
    if candidate.known_malicious:
        return True
    if candidate.requires_credential:      # credential-stealing / secret-exfil shapes
        return True
    if candidate.from_arbitrary_url and not candidate.signed:
        return True                        # unknown unsigned binary from arbitrary URL
    if candidate.risk == AcquisitionRisk.HIGH_RISK and not candidate.signed:
        return True                        # unsigned/unverified high-risk binary
    return False


def decide(candidate: Candidate, *, sandbox_available: bool = True) -> AcquisitionDecision:
    """Map a candidate to an acquisition decision (§143/§153/§154/§163)."""
    if is_forbidden(candidate):
        return AcquisitionDecision.FORBIDDEN
    if candidate.risk == AcquisitionRisk.EXTERNAL:
        return AcquisitionDecision.BLOCKED_BY_EXTERNAL_DEPENDENCY
    if candidate.has_cost or candidate.requires_privilege:
        return AcquisitionDecision.HUMAN_GATE          # §153 cost, §154 privilege
    if candidate.risk == AcquisitionRisk.HIGH_RISK:
        return AcquisitionDecision.HUMAN_GATE
    if candidate.risk == AcquisitionRisk.MEDIUM_RISK and not sandbox_available:
        return AcquisitionDecision.HUMAN_GATE          # needs sandbox/policy control
    return AcquisitionDecision.ACQUIRE                 # LOW_RISK, or MEDIUM in a sandbox


# ---- acquire transaction (§147) ------------------------------------------ #


@dataclass(frozen=True)
class AcquisitionPlan:
    """A candidate plus the injected (sandboxed) install/verify/smoke callables."""

    candidate: Candidate
    install: Callable[[], bool]
    verify: Callable[[], bool]
    smoke: Callable[[], bool]
    rollback: Callable[[], None] = lambda: None
    platform: str = "any"
    install_scope: str = "sandbox"


@dataclass(frozen=True)
class AcquisitionResult:
    state: AcquisitionState
    capability: Capability | None
    tried: tuple[tuple[str, str], ...]   # (candidate_name, decision) audit trail
    evidence: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class AcquisitionEngine:
    registry: CapabilityRegistry
    candidate_limit: int = 5             # §157 bounded — no infinite alternatives

    def acquire(
        self,
        cap_id: str,
        plans: Sequence[AcquisitionPlan],
        *,
        sandbox_available: bool = True,
    ) -> AcquisitionResult:
        """Run the DETECT->...->REGISTER transaction over candidate plans.

        Tries safe candidates in order (bounded by ``candidate_limit``). The first
        that installs+verifies+smokes is registered and returned. A failing
        acquire is rolled back before the next candidate. If none can be safely
        acquired, returns the least-severe terminal reason encountered
        (HUMAN_GATE / BLOCKED_BY_EXTERNAL_DEPENDENCY / FORBIDDEN / FAILED).
        """
        tried: list[tuple[str, str]] = []
        saw_human_gate = saw_external = saw_forbidden = saw_fail = False

        for plan in plans[: self.candidate_limit]:
            d = decide(plan.candidate, sandbox_available=sandbox_available)
            tried.append((plan.candidate.name, d.value))
            if d != AcquisitionDecision.ACQUIRE:
                saw_human_gate |= d == AcquisitionDecision.HUMAN_GATE
                saw_external |= d == AcquisitionDecision.BLOCKED_BY_EXTERNAL_DEPENDENCY
                saw_forbidden |= d == AcquisitionDecision.FORBIDDEN
                continue

            # transaction: install -> verify -> smoke -> promote (rollback on any fail)
            ok = False
            try:
                if plan.install() and plan.verify() and plan.smoke():
                    ok = True
            except Exception:
                ok = False
            if not ok:
                try:
                    plan.rollback()
                except Exception:
                    pass
                saw_fail = True
                continue

            cap = Capability(
                id=cap_id, version=plan.candidate.version, source=plan.candidate.source,
                platform=plan.platform, install_scope=plan.install_scope,
                verification="install+verify+smoke ok", risk=plan.candidate.risk,
                license=plan.candidate.license,
            )
            self.registry.register(cap)
            return AcquisitionResult(
                AcquisitionState.REGISTERED, cap, tuple(tried),
                {"acquired": cap_id, "source": cap.source, "smoke": "ok"},
            )

        if saw_human_gate:
            state = AcquisitionState.HUMAN_GATE
        elif saw_external:
            state = AcquisitionState.BLOCKED_BY_EXTERNAL_DEPENDENCY
        elif saw_fail:
            state = AcquisitionState.FAILED
        elif saw_forbidden:
            state = AcquisitionState.FORBIDDEN
        else:
            state = AcquisitionState.FAILED
        return AcquisitionResult(state, None, tuple(tried), {"reason": state.value})


# ---- DAG dynamic ACQUIRE node (§161) ------------------------------------- #


def acquire_node_id(cap_id: str) -> str:
    return f"__acquire__{cap_id}"


def inject_acquire_node(dag: MissionDag, target_node_id: str, cap_id: str,
                        *, weight: float = 1.0) -> MissionDag:
    """Return a new DAG with an ACQUIRE_<cap> node inserted as a parent of the
    target node (so the target only becomes ready once the capability is
    acquired). Never mutates the input DAG."""
    if target_node_id not in dag:
        raise KeyError(f"unknown target node {target_node_id!r}")
    acq_id = acquire_node_id(cap_id)
    nodes: list[DagNode] = []
    for nid in dag.ids():
        node = dag.node(nid)
        if nid == target_node_id:
            node = replace(node, parents=tuple(node.parents) + (acq_id,))
        nodes.append(node)
    if acq_id not in dag:
        nodes.append(DagNode(id=acq_id, parents=(), weight=weight,
                             label=f"Acquire capability: {cap_id}"))
    return MissionDag(nodes)


__all__ = [
    "AcquisitionRisk", "AcquisitionDecision", "AcquisitionState",
    "Candidate", "Capability", "CapabilityRegistry",
    "AcquisitionPlan", "AcquisitionResult", "AcquisitionEngine",
    "is_forbidden", "decide", "looks_like_missing_capability", "classify_block",
    "acquire_node_id", "inject_acquire_node",
]
