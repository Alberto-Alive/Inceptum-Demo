from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


TABLES = (
    "claims",
    "requests",
    "runs",
    "provenance",
    "investigation_tasks",
    "policies",
)


class JsonSqliteStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def init_schema(self) -> None:
        with self._connect() as connection:
            for table in TABLES:
                connection.execute(
                    f"CREATE TABLE IF NOT EXISTS {table} (record_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
                )
            connection.commit()

    def upsert(self, table: str, record_id: str, payload: dict[str, Any]) -> None:
        self._ensure_table(table)
        encoded = json.dumps(payload, sort_keys=True)
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO {table} (record_id, payload) VALUES (?, ?) "
                f"ON CONFLICT(record_id) DO UPDATE SET payload = excluded.payload",
                (record_id, encoded),
            )
            connection.commit()

    def get(self, table: str, record_id: str) -> dict[str, Any] | None:
        self._ensure_table(table)
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT payload FROM {table} WHERE record_id = ?",
                (record_id,),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["payload"])

    def list(self, table: str) -> list[dict[str, Any]]:
        self._ensure_table(table)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT payload FROM {table} ORDER BY record_id"
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def clear_tables(self, tables: list[str] | tuple[str, ...] | None = None) -> None:
        target_tables = tables or TABLES
        for table in target_tables:
            self._ensure_table(table)
        with self._connect() as connection:
            for table in target_tables:
                connection.execute(f"DELETE FROM {table}")
            connection.commit()

    def _ensure_table(self, table: str) -> None:
        if table not in TABLES:
            raise ValueError(f"Unsupported table: {table}")
