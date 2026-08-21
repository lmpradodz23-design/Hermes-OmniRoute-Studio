"""List OmniRoute MCP/endpoint API routes with a disposable admin token.

Never prints the token. The database row is removed in ``finally``.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import urllib.error
import urllib.request
import uuid
from pathlib import Path


database_path = Path.home() / ".omniroute" / "storage.sqlite"
token_id = f"tok_{uuid.uuid4()}"
token = f"oma_live_{secrets.token_urlsafe(32)}"
created_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
database = sqlite3.connect(database_path)

try:
    database.execute(
        """INSERT INTO cli_access_tokens
        (id, token_hash, token_prefix, name, scope, created_at, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            token_id,
            hashlib.sha256(token.encode()).hexdigest(),
            token[:15],
            "Hermes OpenAPI inspection",
            "admin",
            created_at,
            None,
        ),
    )
    database.commit()

    for pathname in ("/api/openapi.json", "/api/openapi", "/openapi.json"):
        request = urllib.request.Request(
            f"http://127.0.0.1:20128{pathname}",
            headers={"Authorization": f"Bearer {token}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = json.load(response)
            paths = payload.get("paths", {}) if isinstance(payload, dict) else {}
            matches = sorted(
                route
                for route in paths
                if "mcp" in route.lower() or "endpoint" in route.lower()
            )
            print(json.dumps({"source": pathname, "routes": matches}, indent=2))
            break
        except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as error:
            status = getattr(error, "code", "unavailable")
            print(json.dumps({"source": pathname, "status": status}))
finally:
    database.execute("DELETE FROM cli_access_tokens WHERE id = ?", (token_id,))
    database.commit()
    database.close()
