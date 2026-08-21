"""Inspect the local OmniRoute MCP catalog with a disposable admin token.

Only tool names and declared scopes are printed. The credential is never
printed and its database row is removed in ``finally``.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path


database = sqlite3.connect(Path.home() / ".omniroute" / "storage.sqlite")
token_id = f"tok_{uuid.uuid4()}"
token = f"oma_live_{secrets.token_urlsafe(32)}"

try:
    database.execute(
        """INSERT INTO cli_access_tokens
        (id, token_hash, token_prefix, name, scope, created_at, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            token_id,
            hashlib.sha256(token.encode()).hexdigest(),
            token[:15],
            "Hermes MCP catalog inspection",
            "admin",
            datetime.now(timezone.utc).isoformat(),
            None,
        ),
    )
    database.commit()
    request = urllib.request.Request(
        "http://127.0.0.1:20128/api/mcp/tools",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    tools = payload.get("tools", []) if isinstance(payload, dict) else []
    summary = [
        {
            "name": item.get("name"),
            "scopes": item.get("scopes") or item.get("requiredScopes"),
            "keys": sorted(item.keys()),
        }
        for item in tools
        if isinstance(item, dict)
    ]
    print(json.dumps({"count": len(summary), "tools": summary}, indent=2))
finally:
    database.execute("DELETE FROM cli_access_tokens WHERE id = ?", (token_id,))
    database.commit()
    database.close()
