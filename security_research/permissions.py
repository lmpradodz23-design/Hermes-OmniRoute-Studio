"""Matriz de capacidades — mínimo privilégio, por capacidade, com o default
seguro sendo read-only/local/sem exploit.

Cada capacidade do Security Research declara o que precisa. O motor recusa
executar uma capacidade cujas exigências não foram concedidas — o prompt não é
a barreira, a barreira é este gate no ponto de execução.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet


class Capability(str, Enum):
    READ_PROJECT = "read_project"
    WRITE_PROJECT = "write_project"
    EXECUTE_SCANNER = "execute_scanner"
    NETWORK_LOOKUP = "network_lookup"
    EXECUTE_BINARY = "execute_binary"
    FUZZ = "fuzz"
    GENERATE_POC = "generate_poc"
    APPLY_PATCH = "apply_patch"
    SHELL = "shell"
    SSH = "ssh"
    CRON = "cron"


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class CapabilitySpec:
    capability: Capability
    default_granted: bool          # concedida por padrão?
    requires_confirmation: bool    # exige um "sim" explícito do usuário?
    requires_sandbox: bool         # exige isolamento real para rodar?
    network: bool
    write_access: bool
    risk: RiskTier


# O default segue mínimo privilégio: só ler e rodar scanner estático local sem
# confirmação. Tudo que executa alvo, faz rede, escreve ou gera PoC exige
# decisão explícita, e o que executa conteúdo não confiável exige sandbox — que
# no Windows nativo não existe (ver runtime.SandboxProvider).
CAPABILITY_MATRIX: Dict[Capability, CapabilitySpec] = {
    Capability.READ_PROJECT: CapabilitySpec(
        Capability.READ_PROJECT, True, False, False, False, False, RiskTier.LOW
    ),
    Capability.EXECUTE_SCANNER: CapabilitySpec(
        Capability.EXECUTE_SCANNER, True, False, False, False, False, RiskTier.MEDIUM
    ),
    Capability.NETWORK_LOOKUP: CapabilitySpec(
        Capability.NETWORK_LOOKUP, False, True, False, True, False, RiskTier.MEDIUM
    ),
    Capability.WRITE_PROJECT: CapabilitySpec(
        Capability.WRITE_PROJECT, False, True, False, False, True, RiskTier.MEDIUM
    ),
    Capability.EXECUTE_BINARY: CapabilitySpec(
        Capability.EXECUTE_BINARY, False, True, True, False, False, RiskTier.HIGH
    ),
    Capability.FUZZ: CapabilitySpec(
        Capability.FUZZ, False, True, True, False, True, RiskTier.HIGH
    ),
    Capability.GENERATE_POC: CapabilitySpec(
        Capability.GENERATE_POC, False, True, True, False, False, RiskTier.HIGH
    ),
    Capability.APPLY_PATCH: CapabilitySpec(
        Capability.APPLY_PATCH, False, True, False, True, True, RiskTier.HIGH
    ),
    Capability.SHELL: CapabilitySpec(
        Capability.SHELL, False, True, True, False, True, RiskTier.HIGH
    ),
    Capability.SSH: CapabilitySpec(
        Capability.SSH, False, True, False, True, True, RiskTier.HIGH
    ),
    Capability.CRON: CapabilitySpec(
        Capability.CRON, False, True, False, False, False, RiskTier.MEDIUM
    ),
}


class CapabilityDenied(Exception):
    """Uma capacidade foi pedida além do que foi concedido."""


@dataclass
class GrantSet:
    """As capacidades concedidas para uma operação. Default = mínimo privilégio."""

    granted: FrozenSet[Capability] = field(
        default_factory=lambda: frozenset(
            c for c, spec in CAPABILITY_MATRIX.items() if spec.default_granted
        )
    )

    def require(self, capability: Capability) -> None:
        if capability not in self.granted:
            spec = CAPABILITY_MATRIX[capability]
            hint = " (exige confirmação explícita)" if spec.requires_confirmation else ""
            raise CapabilityDenied(f"capacidade não concedida: {capability.value}{hint}")

    def with_granted(self, *caps: Capability) -> "GrantSet":
        return GrantSet(granted=self.granted | set(caps))
