"""Modelo normalizado de finding — e a distinção que o resto do módulo protege:
finding de scanner NÃO é vulnerabilidade confirmada.

Um scanner emite CANDIDATOS. A confirmação exige evidência (validação,
dataflow, reprodução). Por isso todo finding nasce `CANDIDATE` e só a máquina de
estados abaixo — nunca o parser, nunca um LLM — pode movê-lo para `CONFIRMED`.

A camada de evidência separa três coisas que um LLM tende a misturar:
`FACT` (o scanner disse), `INFERENCE` (deduzido de dados), `HYPOTHESIS`
(especulação). Um finding confirmado precisa de pelo menos um FACT reproduzível;
um LLM não pode inventar a evidência ausente.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    UNKNOWN = "unknown"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class FindingState(str, Enum):
    CANDIDATE = "candidate"
    VALIDATING = "validating"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    DISPUTED = "disputed"
    FIXING = "fixing"
    FIXED = "fixed"
    REGRESSION_FAILED = "regression_failed"
    BLOCKED = "blocked"


# Transições permitidas. O que NÃO está aqui é proibido — mover um finding para
# CONFIRMED sem passar por VALIDATING, ou para FIXED sem passar por FIXING, é
# exatamente o "verde artificial" que a missão proíbe.
_ALLOWED_TRANSITIONS: Dict[FindingState, set[FindingState]] = {
    FindingState.CANDIDATE: {
        FindingState.VALIDATING,
        FindingState.FALSE_POSITIVE,
        FindingState.DISPUTED,
        FindingState.BLOCKED,
    },
    FindingState.VALIDATING: {
        FindingState.CONFIRMED,
        FindingState.FALSE_POSITIVE,
        FindingState.DISPUTED,
        FindingState.CANDIDATE,
        FindingState.BLOCKED,
    },
    FindingState.CONFIRMED: {
        FindingState.FIXING,
        FindingState.DISPUTED,
        FindingState.BLOCKED,
    },
    FindingState.FIXING: {
        FindingState.FIXED,
        FindingState.REGRESSION_FAILED,
        FindingState.CONFIRMED,
        FindingState.BLOCKED,
    },
    FindingState.FIXED: {
        FindingState.REGRESSION_FAILED,  # reapareceu
    },
    FindingState.REGRESSION_FAILED: {
        FindingState.FIXING,
        FindingState.CONFIRMED,
    },
    FindingState.DISPUTED: {
        FindingState.VALIDATING,
        FindingState.FALSE_POSITIVE,
        FindingState.CONFIRMED,
    },
    FindingState.FALSE_POSITIVE: set(),  # terminal, mas nunca apagado
    FindingState.BLOCKED: {
        FindingState.CANDIDATE,
        FindingState.VALIDATING,
        FindingState.CONFIRMED,
    },
}


class InvalidTransition(Exception):
    """Tentativa de transição de estado não permitida."""


class EvidenceKind(str, Enum):
    FACT = "fact"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"


@dataclass
class Evidence:
    kind: EvidenceKind
    text: str
    source: str  # scanner/rule/tool que originou — nunca "o LLM disse"


_PATH_NORMALIZE = re.compile(r"[\\/]+")


def fingerprint(
    *,
    scanner: str,
    rule: str,
    normalized_path: str,
    sink: str = "",
    symbol: str = "",
) -> str:
    """Fingerprint estável de deduplicação.

    Dois findings colapsam quando são o MESMO problema: mesmo scanner, mesma
    regra, mesmo arquivo normalizado, mesmo sink/símbolo. NÃO inclui a linha de
    propósito — um shift de linhas por uma edição acima não deve dar
    "vulnerabilidade nova". E NÃO colapsa regras diferentes só porque caem no
    mesmo arquivo: regras diferentes são problemas diferentes.
    """
    norm_path = _PATH_NORMALIZE.sub("/", (normalized_path or "").strip().lower())
    parts = [scanner.strip().lower(), rule.strip().lower(), norm_path, sink.strip().lower(), symbol.strip().lower()]
    return hashlib.sha256("\x1f".join(parts).encode("utf-8", "replace")).hexdigest()[:32]


@dataclass
class Finding:
    """Um finding normalizado, agnóstico de scanner."""

    scanner: str
    rule: str
    severity: Severity
    confidence: Confidence
    file: str
    line: int
    message: str = ""
    project: str = ""
    sink: str = ""
    source: str = ""
    attack_path: List[str] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)
    state: FindingState = FindingState.CANDIDATE
    exploitability: str = "unknown"
    recommended_fix: str = ""
    cwe: Optional[str] = None
    cve: Optional[str] = None
    created_at: float = 0.0
    updated_at: float = 0.0

    @property
    def id(self) -> str:
        return fingerprint(
            scanner=self.scanner, rule=self.rule, normalized_path=self.file, sink=self.sink
        )

    def transition(self, to: FindingState, *, now: float) -> None:
        """Move de estado, recusando transições fora da máquina.

        CONFIRMED exige que já exista pelo menos um FACT na evidência — um
        finding não vira "confirmado" sem nada objetivo por trás.
        """
        if to not in _ALLOWED_TRANSITIONS[self.state]:
            raise InvalidTransition(f"{self.state.value} -> {to.value} não é permitido")
        if to == FindingState.CONFIRMED and not any(e.kind == EvidenceKind.FACT for e in self.evidence):
            raise InvalidTransition("CONFIRMED exige ao menos uma evidência FACT")
        self.state = to
        self.updated_at = now

    def add_evidence(self, kind: EvidenceKind, text: str, source: str) -> None:
        self.evidence.append(Evidence(kind=kind, text=text, source=source))

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["severity"] = self.severity.value
        data["confidence"] = self.confidence.value
        data["state"] = self.state.value
        data["evidence"] = [
            {"kind": e.kind.value, "text": e.text, "source": e.source} for e in self.evidence
        ]
        data["id"] = self.id
        return data


def dedupe(findings: List[Finding]) -> List[Finding]:
    """Colapsa findings com o mesmo fingerprint, preservando o de maior
    severidade/confiança e unindo a evidência. Não perde informação: o
    representante herda a evidência de todos os duplicados."""
    order_sev = {s: i for i, s in enumerate(Severity)}
    order_conf = {c: i for i, c in enumerate(Confidence)}
    by_fp: Dict[str, Finding] = {}
    for f in findings:
        key = f.id
        current = by_fp.get(key)
        if current is None:
            by_fp[key] = f
            continue
        # menor índice = mais severo (CRITICAL=0)
        keep_new = (order_sev[f.severity], order_conf[f.confidence]) < (
            order_sev[current.severity],
            order_conf[current.confidence],
        )
        winner, loser = (f, current) if keep_new else (current, f)
        winner.evidence.extend(loser.evidence)
        by_fp[key] = winner
    return list(by_fp.values())
