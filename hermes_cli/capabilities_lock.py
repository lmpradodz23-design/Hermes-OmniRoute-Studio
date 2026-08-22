"""User-approved integrity lock for executable Hermes capabilities.

The lock is deliberately stored outside the capability directories.  Skills,
plugins and MCP launch descriptors are verified before they can influence the
prompt or execute code.  The file is not a package manager database: it is a
local approval boundary and therefore changes only through an explicit
``hermes capabilities update`` (or an already-approved Skills Hub install).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any, Iterable, Mapping

from hermes_constants import get_hermes_home
from utils import atomic_json_write

LOCK_VERSION = 1
LOCK_FILENAME = "capabilities.lock"
_IGNORED_PARTS = {".hub", "__pycache__", "node_modules"}


class CapabilityIntegrityError(RuntimeError):
    """A capability differs from the exact bytes approved by the user."""


def lock_path(home: Path | None = None) -> Path:
    return Path(home or get_hermes_home()) / LOCK_FILENAME


def _hash_files(paths: Iterable[Path], *, root: Path | None = None) -> str:
    digest = hashlib.sha256()
    original = list(paths)
    for path in original:
        if path.is_symlink():
            raise CapabilityIntegrityError(f"capability contains a symlink: {path}")
    normalized = sorted({path.resolve(strict=True) for path in original}, key=lambda p: str(p).lower())
    for path in normalized:
        if path.is_symlink() or not path.is_file():
            raise CapabilityIntegrityError(f"capability contains an unsupported file: {path}")
        label = path.relative_to(root).as_posix() if root and path.is_relative_to(root) else str(path)
        digest.update(label.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        digest.update(b"\0")
    return digest.hexdigest()


def hash_directory(directory: Path) -> str:
    if directory.is_symlink():
        raise CapabilityIntegrityError(f"capability directory is a symlink: {directory}")
    root = directory.resolve(strict=True)
    if not root.is_dir():
        raise CapabilityIntegrityError(f"capability directory is invalid: {directory}")
    files = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and not any(part in _IGNORED_PARTS for part in path.relative_to(root).parts)
        and path.suffix != ".pyc"
    ]
    return _hash_files(files, root=root)


def _hash_file_content(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise CapabilityIntegrityError(f"capability file is invalid: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _frontmatter(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return {}
    marker = "\n---"
    end = text.find(marker, 4)
    if end < 0:
        return {}
    try:
        import yaml

        parsed = yaml.safe_load(text[4:end]) or {}
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _portable_path(path: Path, home: Path) -> str:
    resolved = path.resolve(strict=False)
    try:
        return resolved.relative_to(home.resolve(strict=False)).as_posix()
    except ValueError:
        return str(resolved)


def _resolve_record_path(value: Any, home: Path) -> Path:
    raw = str(value or "").strip()
    if not raw:
        raise CapabilityIntegrityError("capability lock record has no path")
    candidate = Path(raw)
    return candidate if candidate.is_absolute() else home / candidate


def _skill_records(home: Path) -> list[dict[str, Any]]:
    root = home / "skills"
    if not root.exists():
        return []
    records: list[dict[str, Any]] = []
    for manifest in sorted(root.rglob("SKILL.md"), key=lambda p: str(p).lower()):
        relative_parts = manifest.relative_to(root).parts
        if any(part.startswith(".") or part in _IGNORED_PARTS for part in relative_parts[:-1]):
            continue
        directory = manifest.parent
        metadata = _frontmatter(manifest)
        identifier = directory.relative_to(root).as_posix()
        records.append(
            {
                "id": identifier,
                "source": str(metadata.get("source") or "user"),
                "sha256": hash_directory(directory),
                "version": str(metadata.get("version") or "unversioned"),
                "path": _portable_path(directory, home),
            }
        )
    return records


def _plugin_roots(home: Path) -> list[Path]:
    roots = [home / "plugins"]
    studio = os.environ.get("HERMES_STUDIO_PLUGIN_ROOT", "").strip()
    if studio:
        requested = Path(studio).expanduser().resolve(strict=False)
        current_home = home.resolve(strict=False)
        base_home = (
            current_home.parent.parent
            if current_home.parent.name.lower() == "profiles"
            else current_home
        )
        expected = (base_home / "omniroute-studio" / "plugins").resolve(strict=False)
        if requested == expected:
            roots.append(requested)
    return roots


def _plugin_records(home: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in _plugin_roots(home):
        if not root.exists():
            continue
        for manifest in sorted(root.rglob("plugin.yaml"), key=lambda p: str(p).lower()):
            if any(part.startswith(".") for part in manifest.relative_to(root).parts[:-1]):
                continue
            metadata: dict[str, Any] = {}
            try:
                import yaml

                loaded = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
                metadata = loaded if isinstance(loaded, dict) else {}
            except Exception:
                pass
            identifier = str(metadata.get("name") or manifest.parent.name)
            if identifier in seen:
                continue
            seen.add(identifier)
            records.append(
                {
                    "id": identifier,
                    "sha256": hash_directory(manifest.parent),
                    "version": str(metadata.get("version") or "unversioned"),
                    "security_critical": metadata.get("security_critical") is True,
                    "path": _portable_path(manifest.parent, home),
                }
            )
    return sorted(records, key=lambda item: item["id"])


def _mcp_command_files(config: Mapping[str, Any]) -> list[Path]:
    files: list[Path] = []
    command = str(config.get("command") or "").strip()
    if command:
        resolved = shutil.which(command) or command
        command_path = Path(resolved)
        if command_path.is_file():
            files.append(command_path)
    args = config.get("args")
    if isinstance(args, list):
        for value in args:
            candidate = Path(str(value)).expanduser()
            if candidate.is_file():
                files.append(candidate)
    return files


def mcp_command_hash(config: Mapping[str, Any]) -> str:
    files = _mcp_command_files(config)
    digest = hashlib.sha256()
    descriptor = {
        "command": str(config.get("command") or ""),
        "args": [str(value) for value in config.get("args", [])]
        if isinstance(config.get("args"), list)
        else [],
        "url": str(config.get("url") or ""),
        "transport": str(config.get("transport") or ""),
    }
    digest.update(json.dumps(descriptor, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    digest.update(b"\0")
    if files:
        digest.update(_hash_files(files).encode("ascii"))
    return digest.hexdigest()


def _omniroute_server_metadata() -> dict[str, str]:
    candidates: list[Path] = []
    requested = os.environ.get("OMNIROUTE_PACKAGE_ROOT", "").strip()
    if requested:
        candidates.append(Path(requested))
    omni_executable = shutil.which("omniroute")
    if omni_executable:
        executable = Path(omni_executable)
        candidates.append(executable.parent / "node_modules" / "omniroute")
        try:
            resolved_executable = executable.resolve(strict=True)
            candidates.extend(resolved_executable.parents)
        except OSError:
            pass
    node_executable = shutil.which("node")
    if node_executable:
        candidates.append(Path(node_executable).parent / "node_modules" / "omniroute")
    if os.name == "nt":
        candidates.append(
            Path.home() / "AppData" / "Roaming" / "npm" / "node_modules" / "omniroute"
        )
    else:
        candidates.extend(
            [
                Path("/usr/local/lib/node_modules/omniroute"),
                Path("/usr/lib/node_modules/omniroute"),
                Path.home() / ".npm-global" / "lib" / "node_modules" / "omniroute",
            ]
        )
    for root in candidates:
        server = root / "dist" / "open-sse" / "mcp-server" / "server.js"
        package = root / "package.json"
        if not server.is_file() or not package.is_file():
            continue
        version = "unversioned"
        try:
            payload = json.loads(package.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                version = str(payload.get("version") or version)
        except (OSError, json.JSONDecodeError):
            pass
        return {
            "server_sha256": _hash_file_content(server),
            "server_path": str(server.resolve(strict=True)),
            "version": version,
        }
    return {}


def _mcp_records(servers: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for identifier, raw in sorted(servers.items()):
        if not isinstance(raw, Mapping):
            continue
        record = {
            "id": str(identifier),
            "command_sha256": mcp_command_hash(raw),
            "package": str(raw.get("package") or identifier),
            "version": str(raw.get("version") or "unversioned"),
        }
        if str(identifier).lower() == "omniroute":
            record.update(_omniroute_server_metadata())
        records.append(record)
    return records


def build_snapshot(
    *, home: Path | None = None, mcp_servers: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    resolved_home = Path(home or get_hermes_home())
    if mcp_servers is None:
        try:
            from hermes_cli.config import load_config

            raw = load_config().get("mcp_servers", {})
            mcp_servers = raw if isinstance(raw, dict) else {}
        except Exception:
            mcp_servers = {}
    return {
        "version": LOCK_VERSION,
        "skills": _skill_records(resolved_home),
        "mcp_servers": _mcp_records(mcp_servers),
        "plugins": _plugin_records(resolved_home),
    }


def load_lock(*, home: Path | None = None) -> dict[str, Any] | None:
    path = lock_path(home)
    if not path.exists():
        return None
    if path.is_symlink():
        raise CapabilityIntegrityError(f"capability lock cannot be a symlink: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CapabilityIntegrityError(f"invalid capability lock: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("version") != LOCK_VERSION:
        raise CapabilityIntegrityError("unsupported capability lock schema")
    return payload


def save_lock(snapshot: Mapping[str, Any], *, home: Path | None = None) -> Path:
    path = lock_path(home)
    atomic_json_write(path, dict(snapshot), indent=2, mode=0o600, sort_keys=True)
    return path


def refresh_skill_records(*, home: Path | None = None) -> Path:
    """Update only the skill section after an already-approved Hub mutation."""
    resolved_home = Path(home or get_hermes_home())
    current = load_lock(home=resolved_home)
    if current is None:
        current = build_snapshot(home=resolved_home)
    else:
        current = dict(current)
        current["skills"] = _skill_records(resolved_home)
    return save_lock(current, home=resolved_home)


def _verify_directory_records(records: Any, home: Path, category: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(records, list):
        return [f"{category}: invalid lock records"]
    hash_key = "sha256"
    for record in records:
        if not isinstance(record, dict):
            errors.append(f"{category}: invalid lock record")
            continue
        identifier = str(record.get("id") or "unknown")
        try:
            path = _resolve_record_path(record.get("path"), home)
            actual = hash_directory(path)
        except (OSError, CapabilityIntegrityError) as exc:
            errors.append(f"{category[:-1]} {identifier}: unavailable ({exc})")
            continue
        expected = str(record.get(hash_key) or "")
        if actual != expected:
            errors.append(
                f"{category[:-1]} {identifier}: hash mismatch "
                f"(expected {expected[:12]}, actual {actual[:12]})"
            )
    return errors


def verify_capabilities_lock(
    *,
    home: Path | None = None,
    categories: set[str] | None = None,
    mcp_servers: Mapping[str, Any] | None = None,
) -> None:
    resolved_home = Path(home or get_hermes_home())
    locked = load_lock(home=resolved_home)
    if locked is None:
        return
    selected = categories or {"skills", "plugins", "mcp_servers"}
    errors: list[str] = []
    if "skills" in selected:
        errors.extend(_verify_directory_records(locked.get("skills"), resolved_home, "skills"))
        locked_ids = {
            str(item.get("id"))
            for item in locked.get("skills", [])
            if isinstance(item, dict) and item.get("id")
        }
        current_ids = {item["id"] for item in _skill_records(resolved_home)}
        for identifier in sorted(current_ids - locked_ids):
            errors.append(f"skill {identifier}: not approved by capability lock")
    if "plugins" in selected:
        errors.extend(_verify_directory_records(locked.get("plugins"), resolved_home, "plugins"))
        locked_ids = {
            str(item.get("id"))
            for item in locked.get("plugins", [])
            if isinstance(item, dict) and item.get("id")
        }
        current_ids = {item["id"] for item in _plugin_records(resolved_home)}
        for identifier in sorted(current_ids - locked_ids):
            errors.append(f"plugin {identifier}: not approved by capability lock")
    if "mcp_servers" in selected:
        servers = mcp_servers
        if servers is None:
            try:
                from hermes_cli.config import load_config

                raw = load_config().get("mcp_servers", {})
                servers = raw if isinstance(raw, dict) else {}
            except Exception:
                servers = {}
        current = {item["id"]: item for item in _mcp_records(servers)}
        records = locked.get("mcp_servers")
        if not isinstance(records, list):
            errors.append("mcp_servers: invalid lock records")
        else:
            locked_ids: set[str] = set()
            for record in records:
                if not isinstance(record, dict):
                    errors.append("mcp_server: invalid lock record")
                    continue
                identifier = str(record.get("id") or "unknown")
                locked_ids.add(identifier)
                actual = current.get(identifier)
                if actual is None:
                    errors.append(f"mcp_server {identifier}: unavailable")
                elif actual["command_sha256"] != record.get("command_sha256"):
                    errors.append(f"mcp_server {identifier}: hash mismatch")
                elif actual.get("server_sha256") != record.get("server_sha256"):
                    errors.append(f"mcp_server {identifier}: server hash mismatch")
            for identifier in sorted(current.keys() - locked_ids):
                errors.append(f"mcp_server {identifier}: not approved by capability lock")
    if errors:
        detail = "; ".join(errors)
        raise CapabilityIntegrityError(
            f"BLOCKED capability integrity mismatch: {detail}. "
            "Review the change, then run 'hermes capabilities update'."
        )


def snapshot_diff(old: Mapping[str, Any] | None, new: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []
    if old is None:
        lines.append("+ capability lock v1")
    previous = old or {}
    for category, label in (
        ("skills", "skill"),
        ("plugins", "plugin"),
        ("mcp_servers", "mcp"),
    ):
        before = {
            str(item.get("id")): item
            for item in previous.get(category, [])
            if isinstance(item, dict) and item.get("id")
        }
        after = {
            str(item.get("id")): item
            for item in new.get(category, [])
            if isinstance(item, dict) and item.get("id")
        }
        for identifier in sorted(before.keys() - after.keys()):
            lines.append(f"- {label} {identifier}")
        for identifier in sorted(after.keys() - before.keys()):
            lines.append(f"+ {label} {identifier}")
        for identifier in sorted(before.keys() & after.keys()):
            if before[identifier] != after[identifier]:
                lines.append(f"~ {label} {identifier}")
    return lines
