"""CLI for reviewing and accepting executable capability changes."""

from __future__ import annotations

import argparse
import sys

from hermes_cli.capabilities_lock import (
    CapabilityIntegrityError,
    build_snapshot,
    load_lock,
    save_lock,
    snapshot_diff,
    verify_capabilities_lock,
)


def cmd_capabilities(args: argparse.Namespace) -> int:
    action = getattr(args, "capabilities_action", "verify")
    if action == "verify":
        if load_lock() is None:
            print(
                "Capability integrity: lock is not initialized; run "
                "'hermes capabilities update'.",
                file=sys.stderr,
            )
            return 1
        try:
            verify_capabilities_lock()
        except CapabilityIntegrityError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print("Capability integrity: valid")
        return 0

    current = load_lock()
    proposed = build_snapshot()
    changes = snapshot_diff(current, proposed)
    print("Capability lock changes:")
    print("\n".join(changes) if changes else "  (no changes)")
    if not changes:
        return 0
    if not getattr(args, "yes", False):
        answer = input("Accept these executable capability changes? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            print("Capability lock was not changed.")
            return 1
    destination = save_lock(proposed)
    print(f"Capability lock updated: {destination}")
    return 0


def build_capabilities_parser(subparsers):
    parser = subparsers.add_parser(
        "capabilities",
        help="Verify or explicitly update the capability integrity lock",
    )
    actions = parser.add_subparsers(dest="capabilities_action")
    verify = actions.add_parser("verify", help="Verify skills, plugins and MCP commands")
    verify.set_defaults(func=cmd_capabilities)
    update = actions.add_parser("update", help="Review and accept capability changes")
    update.add_argument("--yes", action="store_true", help="Accept the displayed diff")
    update.set_defaults(func=cmd_capabilities)
    parser.set_defaults(func=cmd_capabilities, capabilities_action="verify")
    return parser
