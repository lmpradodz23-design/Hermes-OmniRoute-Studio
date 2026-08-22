"""Deterministic adversarial corpus for the DZ23 destructive-command boundary.

Nothing in this module executes the generated commands. Every specimen is
passed directly to the security-critical pre-tool hook.
"""

import importlib.util
import itertools
from pathlib import Path

import pytest


def load_plugin():
    root = Path(__file__).resolve().parents[2]
    init = root / "plugins" / "dz23-guardrail" / "__init__.py"
    spec = importlib.util.spec_from_file_location("dz23_guardrail_fuzz_target", init)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def plugin():
    return load_plugin()


DESTRUCTIVE_BASES = (
    "rm -rf /tmp/guardrail-fuzz",
    "rm -fr /tmp/guardrail-fuzz",
    "rm --recursive --force /tmp/guardrail-fuzz",
    r"del /s /q C:\guardrail-fuzz",
    r"rmdir /s /q C:\guardrail-fuzz",
    r"Remove-Item -Recurse -Force C:\guardrail-fuzz",
    "find . -delete",
    "git clean -fdx",
    "git reset --hard HEAD~1",
    "git push origin main --force",
    "DROP TABLE users",
    "drop database production",
    "TRUNCATE TABLE audit_log",
    "docker system prune -af",
    "docker volume prune -f",
    "docker image prune --all",
    "docker rm --force production",
    "Clear-Disk -Number 0 -RemoveData -Confirm:$false",
    r"reg.exe delete HKCU\Software\GuardrailFuzz /f",
    "python -c \"import shutil; shutil.rmtree('/tmp/guardrail-fuzz')\"",
)


WRAPPERS = (
    "{}",
    "sudo {}",
    "env FUZZ=1 {}",
    "bash -c \"{}\"",
    "sh -lc \"{}\"",
    "cmd.exe /d /c \"{}\"",
    "powershell.exe -NoProfile -Command \"{}\"",
    "pwsh -NoLogo -c \"{}\"",
)


REQUIRED_VARIANTS = (
    "$(rm -rf /tmp/guardrail-fuzz)",
    "`rm -rf /tmp/guardrail-fuzz`",
    "echo ready; rm -rf /tmp/guardrail-fuzz",
    "echo ready || rm -rf /tmp/guardrail-fuzz",
    "printf ready | rm -rf /tmp/guardrail-fuzz",
    "echo ready\r\nrm -rf /tmp/guardrail-fuzz",
    "FOO=1 rm -rf /tmp/guardrail-fuzz",
    "FOO=1 BAR=2 rm -rf /tmp/guardrail-fuzz",
    "rm -r -f /tmp/guardrail-fuzz",
    "rm    -rf    /tmp/guardrail-fuzz",
    "rm\t-r\t-f\t/tmp/guardrail-fuzz",
    "rm '-rf' /tmp/guardrail-fuzz",
    'rm "-rf" /tmp/guardrail-fuzz',
    r"del /s /q C:/guardrail-fuzz",
    r"del /s /q \\server\share\guardrail-fuzz",
    r"rmdir /s /q \\server\share\guardrail-fuzz",
    r"Remove-Item -Recurse -Force \\server\share\guardrail-fuzz",
)


def adversarial_commands():
    for base, wrapper in itertools.product(DESTRUCTIVE_BASES, WRAPPERS):
        if '"' in base and wrapper != "{}":
            continue
        wrapped = wrapper.format(base)
        yield wrapped
        yield f"echo ready && {wrapped}"
        yield f"echo ready\n{wrapped}"
        yield wrapped.swapcase()

    yield r"r\m -rf /tmp/guardrail-fuzz"
    yield "r''m -rf /tmp/guardrail-fuzz"
    yield "powershell.exe -EncodedCommand ZgB1AHoAegA="
    yield "pwsh -enc ZgB1AHoAegA="
    yield "echo cm0gLXJmIC90bXAvZ3VhcmRyYWlsLWZ1eno= | base64 --decode | bash"
    yield "Invoke-Expression \"Remove-Item -Recurse -Force C:\\guardrail-fuzz\""
    yield from REQUIRED_VARIANTS


@pytest.mark.parametrize("command", tuple(adversarial_commands()))
def test_adversarial_destructive_variants_are_blocked(plugin, command: str) -> None:
    result = plugin.on_pre_tool_call("terminal", {"command": command})

    assert result is not None, f"destructive variant escaped: {command!r}"
    assert result["action"] == "block", f"variant was not blocked: {command!r}"
    assert "DZ23 Guardrail" in result["message"]


SAFE_COMMANDS = (
    "printf 'rm -rf /tmp/example is forbidden'",
    "echo \"DROP TABLE users\"",
    "cat docs/destructive-commands.md",
    "SELECT 'DROP TABLE users is documented'",
    "git clean -n",
    "git clean --dry-run -dx",
    "npm ci",
    "pip install -r requirements.txt",
    "rm --help",
    "docker system prune --help",
    r"Remove-Item -Recurse -Force -WhatIf C:\guardrail-fuzz",
    "python -m pytest tests/plugins/test_dz23_guardrail_plugin.py",
    "npm run build",
    "git diff --check",
    "Get-ChildItem C:\\guardrail-fuzz",
    "psql -c \"-- DROP TABLE users; migration documentation only\"",
)


@pytest.mark.parametrize("command", SAFE_COMMANDS)
def test_documentation_dry_run_and_verification_commands_are_not_blocked(plugin, command: str) -> None:
    result = plugin.on_pre_tool_call("terminal", {"command": command})

    assert result is None, f"safe command produced a guardrail decision: {command!r} -> {result!r}"


def test_fuzz_corpus_has_material_coverage() -> None:
    corpus = tuple(adversarial_commands())

    assert len(corpus) >= 500
    assert len(set(corpus)) == len(corpus)


@pytest.mark.parametrize(
    "command",
    (
        "pytest",
        "python -m pytest tests/plugins",
        "uv run pytest tests/plugins",
        "npm test",
        "npm run test",
        "npm run lint",
        "npm run typecheck",
        "npm run build",
    ),
)
def test_real_verification_commands_satisfy_the_gate(plugin, command: str) -> None:
    assert plugin._is_verification_command(command) is True


@pytest.mark.parametrize(
    "command",
    (
        "echo npm test",
        "printf 'pytest'",
        "cat docs/testing-with-pytest.md",
        "node -e \"console.log('npm run build')\"",
        "SELECT 'npm test'",
    ),
)
def test_quoted_or_documented_verification_text_does_not_satisfy_the_gate(
    plugin, command: str
) -> None:
    assert plugin._is_verification_command(command) is False
