"""Security Research — motor de DevSecOps do Hermes OmniRoute Studio.

Integra capacidades do RAPTOR (github.com/gadievron/raptor, MIT) ao Hermes SEM
acoplar o core do Hermes ao RAPTOR. O RAPTOR entra por trás de um adapter, como
um provider substituível; o Hermes mantém missão, autorização, observabilidade
e UX.

A fronteira de confiança é dura: código analisado, README, saída de scanner,
SARIF e saída de LLM são ENTRADA NÃO CONFIÁVEL. Nada disso vira instrução ou
comando automaticamente. Ver docs/SECURITY_RESEARCH.md.

Este pacote é puro Python, sem dependência de Electron nem do RAPTOR em import
time — o RAPTOR é descoberto e invocado em runtime, e sua ausência não derruba
o módulo.
"""

from .boundary import (
    AuthorizedTarget,
    ProjectBoundaryError,
    resolve_within_target,
    validate_target_root,
)
from .findings import (
    Finding,
    FindingState,
    Severity,
    Confidence,
    fingerprint,
)

__all__ = [
    "AuthorizedTarget",
    "ProjectBoundaryError",
    "resolve_within_target",
    "validate_target_root",
    "Finding",
    "FindingState",
    "Severity",
    "Confidence",
    "fingerprint",
]
