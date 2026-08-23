"""Matriz de capacidades — mínimo privilégio e negação no ponto de execução."""

import pytest

from security_research.permissions import (
    CAPABILITY_MATRIX,
    Capability,
    CapabilityDenied,
    GrantSet,
    RiskTier,
)


def test_default_grants_are_minimal():
    granted = GrantSet().granted
    # só ler e rodar scanner estático — nada que execute, escreva ou faça rede.
    assert granted == {Capability.READ_PROJECT, Capability.EXECUTE_SCANNER}


@pytest.mark.parametrize(
    "cap",
    [
        Capability.EXECUTE_BINARY,
        Capability.FUZZ,
        Capability.GENERATE_POC,
        Capability.APPLY_PATCH,
        Capability.SHELL,
        Capability.SSH,
        Capability.NETWORK_LOOKUP,
        Capability.WRITE_PROJECT,
    ],
)
def test_invasive_capabilities_denied_by_default(cap):
    with pytest.raises(CapabilityDenied):
        GrantSet().require(cap)


def test_explicit_grant_allows():
    grants = GrantSet().with_granted(Capability.FUZZ)
    grants.require(Capability.FUZZ)  # não levanta


def test_every_high_risk_capability_requires_confirmation():
    for cap, spec in CAPABILITY_MATRIX.items():
        if spec.risk == RiskTier.HIGH:
            assert spec.requires_confirmation, f"{cap.value} de alto risco sem confirmação"
            assert not spec.default_granted, f"{cap.value} de alto risco concedida por padrão"


def test_untrusted_exec_capabilities_require_sandbox():
    for cap in (Capability.EXECUTE_BINARY, Capability.FUZZ, Capability.GENERATE_POC, Capability.SHELL):
        assert CAPABILITY_MATRIX[cap].requires_sandbox
