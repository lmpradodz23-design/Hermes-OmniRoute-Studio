"""Approval policy for dependency changes.

Restoring an existing lockfile is deterministic and may proceed unattended.
Adding a new package changes the project's supply chain and must be surfaced
to the user before any package-manager lifecycle scripts can execute.
"""

from unittest.mock import MagicMock, patch

import pytest

import tools.approval as approval


def _tirith_allow(*_args, **_kwargs):
    return {"action": "allow", "findings": [], "summary": ""}


@pytest.fixture(autouse=True)
def _manual_approval(monkeypatch):
    monkeypatch.setattr(approval, "_get_approval_mode", lambda: "manual")
    monkeypatch.setenv("HERMES_INTERACTIVE", "1")
    approval._session_approved.clear()
    approval._pending.clear()
    approval._permanent_approved.clear()
    yield
    approval._session_approved.clear()
    approval._pending.clear()
    approval._permanent_approved.clear()


@pytest.mark.parametrize(
    "command",
    [
        "npm install left-pad",
        "npm i react@latest",
        "pnpm add zod",
        "yarn add lodash",
        "bun add hono",
        "pip install requests",
        "python -m pip install requests",
        "uv add fastapi",
        "cargo add serde",
        "cargo install ripgrep",
        "gem install rails",
        "go install golang.org/x/tools/gopls@latest",
    ],
)
def test_new_dependency_requires_explicit_approval(command):
    callback = MagicMock(return_value="deny")
    with patch("tools.tirith_security.check_command_security", _tirith_allow):
        result = approval.check_all_command_guards(
            command,
            "local",
            approval_callback=callback,
        )

    assert result["approved"] is False
    callback.assert_called_once()
    assert "depend" in callback.call_args.args[1].lower()


@pytest.mark.parametrize(
    "command",
    [
        "npm ci",
        "npm install",
        "pnpm install --frozen-lockfile",
        "yarn install --immutable",
        "bun install --frozen-lockfile",
        "pip install -r requirements.txt",
        "python -m pip install -r requirements.lock",
        "uv sync --frozen",
        "cargo fetch --locked",
    ],
)
def test_lockfile_restore_does_not_require_dependency_approval(command):
    callback = MagicMock(return_value="deny")
    with patch("tools.tirith_security.check_command_security", _tirith_allow):
        result = approval.check_all_command_guards(
            command,
            "local",
            approval_callback=callback,
        )

    assert result["approved"] is True
    callback.assert_not_called()


def test_known_malware_package_is_blocked_before_human_override():
    callback = MagicMock(return_value="once")
    malware = "BLOCKED: Package 'evil-pkg' (npm) has known malware advisories: MAL-2026-1"

    with (
        patch("tools.tirith_security.check_command_security", _tirith_allow),
        patch("tools.osv_check.check_install_command_for_malware", return_value=malware) as scan,
    ):
        result = approval.check_all_command_guards(
            "npm install evil-pkg",
            "local",
            approval_callback=callback,
        )

    assert result["approved"] is False
    assert result["hard_blocked"] is True
    assert "MAL-2026-1" in result["message"]
    callback.assert_not_called()
    scan.assert_called_once_with("npm install evil-pkg")
