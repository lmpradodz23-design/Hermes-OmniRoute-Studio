"""Durable Mission persistence (Wave 1, §4).

A Mission must survive restart/crash. This is a small SQLite store for the
Mission *reference* record, its DAG nodes + dependency edges, per-node status
and attempts, the latest checkpoint, and an append-only event log. It stores
only ids/status/timestamps/labels/evidence-references — never secrets.

Reuses the pure kernel types (agent.mission / agent.mission_dag). Mirrors the
repo's existing SQLite-per-store pattern (projects_db, kanban_db, spend_ceiling)
rather than introducing a new persistence mechanism.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from agent.mission import Checkpoint, Mission, MissionState
from agent.mission_dag import DagNode, MissionDag

_SCHEMA = """
CREATE TABLE IF NOT EXISTS missions (
  id TEXT PRIMARY KEY, title TEXT, state TEXT, goal_key TEXT,
  kanban_board_id TEXT, created_at REAL, updated_at REAL,
  human_gate INTEGER DEFAULT 0, meta_json TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS mission_nodes (
  mission_id TEXT, node_id TEXT, label TEXT, weight REAL DEFAULT 1.0,
  status TEXT DEFAULT 'pending', attempts INTEGER DEFAULT 0,
  evidence_ref TEXT, PRIMARY KEY (mission_id, node_id)
);
CREATE TABLE IF NOT EXISTS mission_deps (
  mission_id TEXT, node_id TEXT, parent_id TEXT,
  PRIMARY KEY (mission_id, node_id, parent_id)
);
CREATE TABLE IF NOT EXISTS mission_checkpoints (
  mission_id TEXT PRIMARY KEY, state TEXT, at REAL,
  goal_key TEXT, kanban_board_id TEXT
);
CREATE TABLE IF NOT EXISTS mission_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT, at REAL,
  kind TEXT, detail_json TEXT DEFAULT '{}'
);
"""


class MissionStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ---- missions ------------------------------------------------------- #

    def save_mission(
        self,
        mission: Mission,
        dag: MissionDag,
        statuses: dict[str, str] | None = None,
    ) -> None:
        statuses = statuses or {}
        c = self._conn
        c.execute(
            "INSERT OR REPLACE INTO missions "
            "(id,title,state,goal_key,kanban_board_id,created_at,updated_at,human_gate,meta_json) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                mission.id, mission.title, mission.state.value, mission.goal_key,
                mission.kanban_board_id, mission.created_at, mission.updated_at,
                1 if mission.human_gate else 0, json.dumps(dict(mission.meta)),
            ),
        )
        # replace node/dep rows for this mission
        c.execute("DELETE FROM mission_deps WHERE mission_id=?", (mission.id,))
        for nid in dag.ids():
            node = dag.node(nid)
            existing = c.execute(
                "SELECT status,attempts,evidence_ref FROM mission_nodes WHERE mission_id=? AND node_id=?",
                (mission.id, nid),
            ).fetchone()
            status = statuses.get(nid) or (existing["status"] if existing else "pending")
            attempts = existing["attempts"] if existing else 0
            evref = existing["evidence_ref"] if existing else None
            c.execute(
                "INSERT OR REPLACE INTO mission_nodes "
                "(mission_id,node_id,label,weight,status,attempts,evidence_ref) VALUES (?,?,?,?,?,?,?)",
                (mission.id, nid, node.label, node.weight, status, attempts, evref),
            )
            for parent in node.parents:
                c.execute(
                    "INSERT OR REPLACE INTO mission_deps (mission_id,node_id,parent_id) VALUES (?,?,?)",
                    (mission.id, nid, parent),
                )
        c.commit()

    def load_mission(self, mission_id: str) -> tuple[Mission, MissionDag, dict[str, str]]:
        c = self._conn
        row = c.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
        if row is None:
            raise KeyError(f"no mission {mission_id!r}")
        mission = Mission(
            id=row["id"], title=row["title"] or "",
            state=MissionState(row["state"]), goal_key=row["goal_key"],
            kanban_board_id=row["kanban_board_id"], created_at=row["created_at"],
            updated_at=row["updated_at"], human_gate=bool(row["human_gate"]),
            meta=json.loads(row["meta_json"] or "{}"),
        )
        deps: dict[str, list[str]] = {}
        for d in c.execute("SELECT node_id,parent_id FROM mission_deps WHERE mission_id=?", (mission_id,)):
            deps.setdefault(d["node_id"], []).append(d["parent_id"])
        nodes: list[DagNode] = []
        statuses: dict[str, str] = {}
        for n in c.execute("SELECT * FROM mission_nodes WHERE mission_id=?", (mission_id,)):
            nodes.append(
                DagNode(id=n["node_id"], parents=tuple(deps.get(n["node_id"], ())),
                        weight=n["weight"], label=n["label"] or "")
            )
            statuses[n["node_id"]] = n["status"]
        return mission, MissionDag(nodes), statuses

    def set_node_status(
        self, mission_id: str, node_id: str, status: str,
        *, attempts: int | None = None, evidence_ref: str | None = None,
    ) -> None:
        sets = ["status=?"]
        args: list[Any] = [status]
        if attempts is not None:
            sets.append("attempts=?"); args.append(attempts)
        if evidence_ref is not None:
            sets.append("evidence_ref=?"); args.append(evidence_ref)
        args.extend([mission_id, node_id])
        self._conn.execute(
            f"UPDATE mission_nodes SET {','.join(sets)} WHERE mission_id=? AND node_id=?", args
        )
        self._conn.commit()

    def node_row(self, mission_id: str, node_id: str) -> dict[str, Any]:
        r = self._conn.execute(
            "SELECT * FROM mission_nodes WHERE mission_id=? AND node_id=?",
            (mission_id, node_id),
        ).fetchone()
        return dict(r) if r else {}

    def update_mission_state(self, mission_id: str, state: MissionState, *, at: float | None = None,
                             human_gate: bool | None = None) -> None:
        sets = ["state=?", "updated_at=?"]
        args: list[Any] = [state.value, at]
        if human_gate is not None:
            sets.append("human_gate=?"); args.append(1 if human_gate else 0)
        args.append(mission_id)
        self._conn.execute(f"UPDATE missions SET {','.join(sets)} WHERE id=?", args)
        self._conn.commit()

    # ---- checkpoints / events ------------------------------------------ #

    def save_checkpoint(self, cp: Checkpoint) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO mission_checkpoints "
            "(mission_id,state,at,goal_key,kanban_board_id) VALUES (?,?,?,?,?)",
            (cp.mission_id, cp.state.value, cp.at, cp.goal_key, cp.kanban_board_id),
        )
        self._conn.commit()

    def load_checkpoint(self, mission_id: str) -> Checkpoint | None:
        r = self._conn.execute(
            "SELECT * FROM mission_checkpoints WHERE mission_id=?", (mission_id,)
        ).fetchone()
        if r is None:
            return None
        return Checkpoint(
            mission_id=r["mission_id"], goal_key=r["goal_key"],
            kanban_board_id=r["kanban_board_id"], state=MissionState(r["state"]), at=r["at"],
        )

    def append_event(self, mission_id: str, kind: str, detail: dict[str, Any] | None = None,
                     *, at: float | None = None) -> None:
        self._conn.execute(
            "INSERT INTO mission_events (mission_id,at,kind,detail_json) VALUES (?,?,?,?)",
            (mission_id, at, kind, json.dumps(detail or {})),
        )
        self._conn.commit()

    def events(self, mission_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT at,kind,detail_json FROM mission_events WHERE mission_id=? ORDER BY id", (mission_id,)
        ).fetchall()
        return [
            {"at": r["at"], "kind": r["kind"], "detail": json.loads(r["detail_json"] or "{}")}
            for r in rows
        ]


__all__ = ["MissionStore"]
