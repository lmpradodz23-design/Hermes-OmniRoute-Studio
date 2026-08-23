"""Adapter do RAPTOR — contrato de argv, gate de plataforma, e (quando o
RAPTOR está presente) uma execução real do modo plano `describe`.
"""

import os
import shutil
from pathlib import Path

import pytest

from security_research.adapter import (
    PlatformSecurityBlocked,
    RaptorAdapter,
    RaptorMode,
)
from security_research.boundary import AuthorizedTarget
from security_research.permissions import Capability, CapabilityDenied, GrantSet
from security_research.runtime import SandboxBackend, SandboxCapabilities

RAPTOR_ROOT = os.environ.get("RAPTOR_ROOT", "/tmp/raptor")


@pytest.fixture
def target(tmp_path):
    (tmp_path / "app.py").write_text("import subprocess\nsubprocess.run('x', shell=True)\n")
    return AuthorizedTarget.create(str(tmp_path))


def _no_sandbox():
    return SandboxCapabilities(SandboxBackend.WINDOWS_RESTRICTED, False, "sem isolamento (teste)")


def _with_sandbox():
    return SandboxCapabilities(SandboxBackend.LINUX_NAMESPACES, True, "isolado (teste)")


# ── contrato de argv (command injection defense) ─────────────────────────


def test_scan_argv_is_a_token_list_never_a_shell_string(target):
    adapter = RaptorAdapter(RAPTOR_ROOT, sandbox=_with_sandbox())
    if not adapter.info().available:
        pytest.skip("RAPTOR não disponível")
    argv = adapter.scan_argv(target, GrantSet(), "/tmp/out")
    assert isinstance(argv, list)
    assert all(isinstance(t, str) for t in argv)
    # o caminho do alvo é UM token, não interpolado numa string
    assert str(target.root) in argv
    # CodeQL desligado por padrão (restrição de licença)
    assert "--no-codeql" in argv


def test_scan_requires_scanner_capability(target):
    adapter = RaptorAdapter(RAPTOR_ROOT, sandbox=_with_sandbox())
    empty = GrantSet(granted=frozenset())
    with pytest.raises(CapabilityDenied):
        adapter.scan_argv(target, empty, "/tmp/out")


# ── gate de plataforma (sandbox Linux/macOS, não Windows) ────────────────


def test_untrusted_exec_blocked_without_sandbox(target):
    adapter = RaptorAdapter(RAPTOR_ROOT, sandbox=_no_sandbox())
    grants = GrantSet().with_granted(Capability.FUZZ, Capability.EXECUTE_BINARY, Capability.GENERATE_POC)
    for mode in (RaptorMode.FUZZ, RaptorMode.BINARY, RaptorMode.EXPLOIT, RaptorMode.CRASH, RaptorMode.FRIDA):
        with pytest.raises(PlatformSecurityBlocked):
            adapter._guard_mode(mode, grants)


def test_static_modes_allowed_without_sandbox(target):
    # scan/describe/sca não executam conteúdo não confiável → não exigem sandbox.
    adapter = RaptorAdapter(RAPTOR_ROOT, sandbox=_no_sandbox())
    adapter._guard_mode(RaptorMode.DESCRIBE, GrantSet())
    adapter._guard_mode(RaptorMode.SCAN, GrantSet())


# ── execução real (prova de integração) ──────────────────────────────────


@pytest.mark.skipif(
    not (Path(RAPTOR_ROOT) / "raptor.py").is_file() or not shutil.which("python3"),
    reason="RAPTOR checkout ausente",
)
def test_real_raptor_describe_runs(target):
    """Prova viva: o adapter invoca o RAPTOR real e recebe JSON estruturado.

    Este é o "RAPTOR integrado", não "RAPTOR instalado ao lado": o describe é
    invocado por argv, dentro da fronteira, e a saída volta normalizável.
    """
    adapter = RaptorAdapter(RAPTOR_ROOT, sandbox=_with_sandbox())
    if not adapter.info().available:
        pytest.skip("RAPTOR não disponível")
    result = adapter.describe(target, GrantSet(), timeout=120)
    assert result["primary_language"] == "python"
    assert result["target_path"] == str(target.root)
    assert "tool_checks" in result  # preflight de ferramentas presente
