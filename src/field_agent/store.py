"""SQLite persistence for updates, proposed actions, and the approval outbox.

SQLite keeps the prototype dependency-free. FastAPI runs sync endpoints on a thread
pool and every thread shares one connection, so *every* statement (reads included)
goes through one re-entrant lock. Without that, interleaved statements on the shared
connection returned wrong rows or None (issue #3). A connection per request would
allow parallel reads; at prototype scale the single lock is simpler and correct.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .schemas import (
    ActionStatus,
    ActionType,
    ExtractionResult,
    GuardrailReport,
    ProposedAction,
    ScheduleConflict,
    UpdateRecord,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS updates (
  id TEXT PRIMARY KEY,
  received_at TEXT NOT NULL,
  message TEXT NOT NULL,
  message_fingerprint TEXT NOT NULL,
  extraction TEXT NOT NULL,
  guardrails TEXT NOT NULL,
  conflicts TEXT NOT NULL DEFAULT '[]',
  provider TEXT NOT NULL,
  model TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS actions (
  id TEXT PRIMARY KEY,
  update_id TEXT NOT NULL REFERENCES updates(id),
  type TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending_approval', 'approved', 'rejected')),
  summary TEXT NOT NULL,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  reviewed_by TEXT,
  reviewed_at TEXT,
  review_note TEXT
);
CREATE INDEX IF NOT EXISTS actions_status ON actions(status);
-- Approved actions land here for a downstream integration to pick up. Nothing reads it in this prototype.
CREATE TABLE IF NOT EXISTS outbox (
  id TEXT PRIMARY KEY,
  action_id TEXT NOT NULL REFERENCES actions(id),
  created_at TEXT NOT NULL,
  payload TEXT NOT NULL
);
"""


class NotFound(Exception):
    pass


class AlreadyReviewed(Exception):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Store:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._lock = threading.RLock()

    def save_update(
        self,
        *,
        message: str,
        message_fingerprint: str,
        extraction: ExtractionResult,
        guardrails: GuardrailReport,
        provider: str,
        model: str,
        actions: list[tuple[ActionType, str, dict[str, Any]]],
        conflicts: list[ScheduleConflict] | None = None,
    ) -> UpdateRecord:
        update_id = uuid.uuid4().hex[:16]
        now = _now()
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO updates (id, received_at, message, message_fingerprint, extraction, guardrails, conflicts, "
                "provider, model) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    update_id,
                    now,
                    message,
                    message_fingerprint,
                    extraction.model_dump_json(),
                    guardrails.model_dump_json(),
                    json.dumps([c.model_dump(mode="json") for c in conflicts or []]),
                    provider,
                    model,
                ),
            )
            for action_type, summary, payload in actions:
                self._conn.execute(
                    "INSERT INTO actions (id, update_id, type, status, summary, payload, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        uuid.uuid4().hex[:16],
                        update_id,
                        action_type.value,
                        ActionStatus.pending_approval.value,
                        summary,
                        json.dumps(payload),
                        now,
                    ),
                )
        return self.get_update(update_id)

    def get_update(self, update_id: str) -> UpdateRecord:
        with self._lock:
            row = self._conn.execute("SELECT * FROM updates WHERE id = ?", (update_id,)).fetchone()
            if row is None:
                raise NotFound(update_id)
            actions = self._conn.execute("SELECT * FROM actions WHERE update_id = ? ORDER BY rowid", (update_id,)).fetchall()
            return UpdateRecord(
                id=row["id"],
                received_at=row["received_at"],
                message_redacted=row["message"],
                message_fingerprint=row["message_fingerprint"],
                extraction=ExtractionResult.model_validate_json(row["extraction"]),
                guardrails=GuardrailReport.model_validate_json(row["guardrails"]),
                conflicts=[ScheduleConflict.model_validate(c) for c in json.loads(row["conflicts"])],
                provider=row["provider"],
                model=row["model"],
                actions=[self._action(a) for a in actions],
            )

    def list_actions(self, status: ActionStatus | None = None, limit: int = 100) -> list[ProposedAction]:
        with self._lock:
            if status:
                rows = self._conn.execute(
                    "SELECT * FROM actions WHERE status = ? ORDER BY created_at DESC LIMIT ?", (status.value, limit)
                ).fetchall()
            else:
                rows = self._conn.execute("SELECT * FROM actions ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [self._action(r) for r in rows]

    def review(self, action_id: str, decision: ActionStatus, reviewer: str, note: str | None) -> ProposedAction:
        if decision is ActionStatus.pending_approval:
            raise ValueError("decision must be approved or rejected")
        now = _now()
        with self._lock, self._conn:
            # Conditional update: only a pending action can be reviewed, and only once.
            cur = self._conn.execute(
                "UPDATE actions SET status = ?, reviewed_by = ?, reviewed_at = ?, review_note = ? "
                "WHERE id = ? AND status = 'pending_approval'",
                (decision.value, reviewer, now, note, action_id),
            )
            if cur.rowcount == 0:
                exists = self._conn.execute("SELECT 1 FROM actions WHERE id = ?", (action_id,)).fetchone()
                raise AlreadyReviewed(action_id) if exists else NotFound(action_id)
            if decision is ActionStatus.approved:
                row = self._conn.execute("SELECT type, payload FROM actions WHERE id = ?", (action_id,)).fetchone()
                self._conn.execute(
                    "INSERT INTO outbox VALUES (?, ?, ?, ?)",
                    (
                        uuid.uuid4().hex[:16],
                        action_id,
                        now,
                        json.dumps({"type": row["type"], "payload": json.loads(row["payload"]), "approved_by": reviewer}),
                    ),
                )
        return self.get_action(action_id)

    def get_action(self, action_id: str) -> ProposedAction:
        with self._lock:
            row = self._conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
            if row is None:
                raise NotFound(action_id)
            return self._action(row)

    def outbox_count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]

    @staticmethod
    def _action(row: sqlite3.Row) -> ProposedAction:
        return ProposedAction(
            id=row["id"],
            update_id=row["update_id"],
            type=row["type"],
            status=row["status"],
            summary=row["summary"],
            payload=json.loads(row["payload"]),
            created_at=row["created_at"],
            reviewed_by=row["reviewed_by"],
            reviewed_at=row["reviewed_at"],
            review_note=row["review_note"],
        )
