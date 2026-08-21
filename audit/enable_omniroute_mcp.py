"""Enable OmniRoute's local MCP HTTP transport with a disposable admin token."""

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
            "Hermes MCP bootstrap",
            "admin",
            datetime.now(timezone.utc).isoformat(),
            None,
        ),
    )
    database.commit()
    request = urllib.request.Request(
        "http://127.0.0.1:20128/api/settings",
        method="PATCH",
        data=json.dumps(
            {"mcpEnabled": True, "mcpTransport": "streamable-http"}
        ).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    print(
        json.dumps(
            {
                "http_status": response.status,
                "mcpEnabled": payload.get("mcpEnabled", True),
                "mcpTransport": payload.get("mcpTransport", "streamable-http"),
            }
        )
    )
finally:
    database.execute("DELETE FROM cli_access_tokens WHERE id = ?", (token_id,))
    database.commit()
    database.close()
