from __future__ import annotations

import sqlite3
from pathlib import Path


class StateStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS event_mappings (
                    source_id TEXT PRIMARY KEY,
                    google_event_id TEXT NOT NULL,
                    last_synced_hash TEXT
                )
                """
            )

    def get_google_event_id(self, source_id: str) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT google_event_id FROM event_mappings WHERE source_id = ?",
                (source_id,),
            ).fetchone()
        return row[0] if row else None

    def get_mapping(self, source_id: str) -> tuple[str, str | None] | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT google_event_id, last_synced_hash
                FROM event_mappings
                WHERE source_id = ?
                """,
                (source_id,),
            ).fetchone()
        if row is None:
            return None
        return row[0], row[1]

    def save_mapping(
        self, source_id: str, google_event_id: str, last_synced_hash: str | None = None
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO event_mappings (source_id, google_event_id, last_synced_hash)
                VALUES (?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    google_event_id = excluded.google_event_id,
                    last_synced_hash = excluded.last_synced_hash
                """,
                (source_id, google_event_id, last_synced_hash),
            )
