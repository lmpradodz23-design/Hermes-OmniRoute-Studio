"""Read-only state.db integrity probe. Invoked by windows-validation.ps1.

Opens the database in READ-ONLY mode (mode=ro) and runs PRAGMA quick_check and
PRAGMA integrity_check. Never writes, migrates, VACUUMs, or repairs. Prints a
single machine-readable line.

Usage: python state-db-check.py <path-to-state.db>
"""
import sqlite3
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("ERROR missing db path")
        return 2
    db = sys.argv[1]
    try:
        # uri read-only: guarantees no write/create can occur.
        con = sqlite3.connect("file:" + db + "?mode=ro", uri=True)
    except Exception as exc:  # noqa: BLE001
        print("ERROR open " + str(exc))
        return 3
    try:
        quick = con.execute("PRAGMA quick_check").fetchone()
        integ = con.execute("PRAGMA integrity_check").fetchone()
        qv = quick[0] if quick else "?"
        iv = integ[0] if integ else "?"
        print("quick_check=" + str(qv) + " integrity_check=" + str(iv))
        return 0
    except Exception as exc:  # noqa: BLE001
        print("ERROR pragma " + str(exc))
        return 4
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())
