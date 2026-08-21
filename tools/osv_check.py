"""OSV malware check for MCP extension packages.

Before launching an MCP server via npx/uvx, queries the OSV (Open Source
Vulnerabilities) API to check if the package has any known malware advisories
(MAL-* IDs).  Regular CVEs are ignored — only confirmed malware is blocked.

The API is free, public, and maintained by Google.  Typical latency is ~300ms.
Fail-open: network errors allow the package to proceed.

Inspired by Block/goose's extension malware check.
"""

import json
import logging
import os
import re
import shlex
import threading
import time
import urllib.request
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_OSV_ENDPOINT = os.getenv("OSV_ENDPOINT", "https://api.osv.dev/v1/query")
_TIMEOUT = 10  # seconds

# Result cache: (ecosystem, package, version) -> (expiry_monotonic, result).
# MCP reconnect ladders, stdio recycles, and parked-server self-probes re-run
# the preflight for the SAME package on every spawn attempt. Without a cache,
# a flapping server turns into a sustained OSV query/DNS stream — the #75485
# incident logged 779K api.osv.dev DNS queries in 16h from revival loops.
# Malware advisories don't appear or vanish on second-to-second timescales,
# so a successful verdict (clean OR blocked) is reusable. Network failures
# are NOT cached: fail-open already covers them, and caching a failure could
# mask a real advisory once connectivity returns.
_CACHE_TTL_S = float(os.getenv("OSV_CHECK_CACHE_TTL", "3600"))
_CACHE_MAX_ENTRIES = 256
_cache: dict = {}
_cache_lock = threading.Lock()


def _cache_get(key) -> Tuple[bool, Optional[str]]:
    """Return (hit, result) for a fresh cache entry."""
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return False, None
        expiry, result = entry
        if time.monotonic() >= expiry:
            del _cache[key]
            return False, None
        return True, result


def _cache_put(key, result: Optional[str]) -> None:
    with _cache_lock:
        if len(_cache) >= _CACHE_MAX_ENTRIES:
            now = time.monotonic()
            for k in [k for k, (exp, _) in _cache.items() if exp <= now]:
                del _cache[k]
            if len(_cache) >= _CACHE_MAX_ENTRIES:
                _cache.clear()  # tiny working set in practice; safe reset
        _cache[key] = (time.monotonic() + _CACHE_TTL_S, result)


def check_package_for_malware(
    command: str, args: list
) -> Optional[str]:
    """Check if an MCP server package has known malware advisories.

    Inspects the *command* (e.g. ``npx``, ``uvx``) and *args* to infer the
    package name and ecosystem.  Queries the OSV API for MAL-* advisories.

    Returns:
        An error message string if malware is found, or None if clean/unknown.
        Returns None (allow) on network errors or unrecognized commands.
    """
    ecosystem = _infer_ecosystem(command)
    if not ecosystem:
        return None  # not npx/uvx — skip

    package, version = _parse_package_from_args(args, ecosystem)
    if not package:
        return None

    return _check_package_identity_for_malware(package, ecosystem, version)


def _check_package_identity_for_malware(
    package: str, ecosystem: str, version: Optional[str] = None
) -> Optional[str]:
    """Query/cache one normalized package identity."""
    cache_key = (ecosystem, package, version)
    hit, cached = _cache_get(cache_key)
    if hit:
        return cached

    try:
        malware = _query_osv(package, ecosystem, version)
    except Exception as exc:
        # Fail-open: network errors, timeouts, parse failures → allow.
        # Deliberately NOT cached — see _CACHE_TTL_S comment.
        logger.debug("OSV check failed for %s/%s (allowing): %s", ecosystem, package, exc)
        return None

    if malware:
        ids = ", ".join(m["id"] for m in malware[:3])
        summaries = "; ".join(
            m.get("summary", m["id"])[:100] for m in malware[:3]
        )
        result = (
            f"BLOCKED: Package '{package}' ({ecosystem}) has known malware "
            f"advisories: {ids}. Details: {summaries}"
        )
    else:
        result = None
    _cache_put(cache_key, result)
    return result


_INSTALL_ECOSYSTEMS = {
    "cargo": "crates.io",
    "gem": "RubyGems",
    "go": "Go",
}


def _first_package_token(args: list[str]) -> Optional[str]:
    """Return the first package-shaped token, ignoring CLI options.

    This intentionally handles only the dependency-add commands gated by
    ``tools.approval``. Lockfile/requirements restores are excluded before
    this helper is called.
    """
    for arg in args:
        if not arg or arg.startswith("-"):
            continue
        return arg.strip("\"'")
    return None


def check_install_command_for_malware(command: str) -> Optional[str]:
    """Scan a regular package-manager add/install command via OSV.

    Unlike :func:`check_package_for_malware`, which protects MCP ``npx`` and
    ``uvx`` launches, this entry point covers dependency changes initiated in
    the terminal. It returns a hard-block message only for a confirmed MAL-*
    advisory. Unparseable commands and temporary network failures still fall
    through to the separate human-approval boundary.
    """
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return None
    if not tokens:
        return None

    lowered = [token.lower() for token in tokens]
    start = 0
    if len(tokens) >= 4 and lowered[0] in {"python", "python3", "py"} and lowered[1:3] == ["-m", "pip"]:
        manager = "pip"
        start = 3
    elif len(tokens) >= 4 and lowered[0] == "uv" and lowered[1:3] == ["pip", "install"]:
        manager = "pip"
        start = 2
    else:
        manager = os.path.basename(lowered[0]).removesuffix(".cmd").removesuffix(".exe")
        start = 1

    if start >= len(tokens):
        return None
    action = lowered[start]
    args = tokens[start + 1:]

    ecosystem: Optional[str] = None
    if manager in {"npm", "pnpm"} and action in {"add", "i", "install"}:
        ecosystem = "npm"
    elif manager in {"yarn", "bun"} and action == "add":
        ecosystem = "npm"
    elif manager == "pip" and action == "install":
        if any(arg in {"-r", "--requirement"} or arg.startswith("--requirement=") for arg in args):
            return None
        ecosystem = "PyPI"
    elif manager == "uv" and action == "add":
        ecosystem = "PyPI"
    elif manager in {"poetry", "pdm"} and action == "add":
        ecosystem = "PyPI"
    elif manager in _INSTALL_ECOSYSTEMS and (
        (manager == "cargo" and action in {"add", "install"})
        or (manager in {"gem", "go"} and action == "install")
    ):
        ecosystem = _INSTALL_ECOSYSTEMS[manager]
    else:
        return None

    token = _first_package_token(args)
    if not token or token in {".", ".."} or token.startswith(("./", "../")):
        return None

    if ecosystem == "npm":
        package, version = _parse_npm_package(token)
    elif ecosystem == "PyPI":
        package, version = _parse_pypi_package(token)
    else:
        # Go module versions and Ruby/Cargo package versions all use an @
        # suffix in their common CLI form. Preserve scoped npm parsing above.
        package, sep, raw_version = token.rpartition("@")
        if not sep or not package:
            package, version = token, None
        else:
            version = None if raw_version == "latest" else raw_version

    if not package:
        return None
    return _check_package_identity_for_malware(package, ecosystem, version)


def _infer_ecosystem(command: str) -> Optional[str]:
    """Infer package ecosystem from the command name."""
    base = os.path.basename(command).lower()
    if base in {"npx", "npx.cmd"}:
        return "npm"
    if base in {"uvx", "uvx.cmd", "pipx"}:
        return "PyPI"
    return None


def _parse_package_from_args(
    args: list, ecosystem: str
) -> Tuple[Optional[str], Optional[str]]:
    """Extract package name and optional version from command args.

    Returns (package_name, version) or (None, None) if not parseable.
    """
    if not args:
        return None, None

    # Skip flags to find the package token.
    # Honor npx's explicit install target: --package=NAME / --package NAME and
    # the -p NAME short form, which name a package distinct from the executed
    # binary. Without this the first bare positional (often the command name)
    # is mistaken for the package.
    package_token = None
    take_next = False
    for arg in args:
        if not isinstance(arg, str):
            continue
        if take_next:
            package_token = arg
            break
        if arg in ("--package", "-p"):
            take_next = True
            continue
        if arg.startswith("--package="):
            package_token = arg[len("--package="):]
            break
        if arg.startswith("-"):
            continue
        package_token = arg
        break

    if not package_token:
        return None, None

    if ecosystem == "npm":
        return _parse_npm_package(package_token)
    elif ecosystem == "PyPI":
        return _parse_pypi_package(package_token)
    return package_token, None


def _parse_npm_package(token: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse npm package: @scope/name@version or name@version."""
    if token.startswith("@"):
        # Scoped: @scope/name@version
        match = re.match(r"^(@[^/]+/[^@]+)(?:@(.+))?$", token)
        if match:
            return match.group(1), match.group(2)
        return token, None
    # Unscoped: name@version
    if "@" in token:
        parts = token.rsplit("@", 1)
        name = parts[0]
        version = parts[1] if len(parts) > 1 and parts[1] != "latest" else None
        return name, version
    return token, None


def _parse_pypi_package(token: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse PyPI package: name==version or name[extras]==version."""
    # Strip extras: name[extra1,extra2]==version
    match = re.match(r"^([a-zA-Z0-9._-]+)(?:\[[^\]]*\])?(?:==(.+))?$", token)
    if match:
        return match.group(1), match.group(2)
    return token, None


def _query_osv(
    package: str, ecosystem: str, version: Optional[str] = None
) -> list:
    """Query the OSV API for MAL-* advisories. Returns list of malware vulns."""
    payload = {"package": {"name": package, "ecosystem": ecosystem}}
    if version:
        payload["version"] = version

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        _OSV_ENDPOINT,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "hermes-agent-osv-check/1.0",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        result = json.loads(resp.read())

    vulns = result.get("vulns", [])
    # Only malware advisories — ignore regular CVEs
    return [v for v in vulns if v.get("id", "").startswith("MAL-")]
