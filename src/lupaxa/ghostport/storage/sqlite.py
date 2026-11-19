"""SQLite state that survives a process restart. History is not stored here."""

from __future__ import annotations

import copy
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from lupaxa.ghostport.config.models import StateDef


class SqliteStore:
    """One database file for the collections and values of one API engine."""

    def __init__(self, path: Path, state: StateDef) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._initial = state
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS records (collection TEXT, key TEXT, body TEXT, "
            "position INTEGER, PRIMARY KEY (collection, key))"
        )
        self._conn.execute("CREATE TABLE IF NOT EXISTS values_ (name TEXT PRIMARY KEY, body TEXT)")
        self._conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        seeded = self._conn.execute("SELECT value FROM meta WHERE key = 'seeded'").fetchone()
        if seeded is None:
            self._write_initial()
            self._conn.execute("INSERT INTO meta (key, value) VALUES ('seeded', '1')")
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def reset(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM records")
            self._conn.execute("DELETE FROM values_")
            self._write_initial()
            self._conn.commit()

    def list_records(self, name: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT body FROM records WHERE collection = ? ORDER BY position",
                (name,),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def get_record(self, name: str, key: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT body FROM records WHERE collection = ? AND key = ?",
                (name, key),
            ).fetchone()
        return None if row is None else json.loads(row[0])

    def create_record(self, name: str, record: dict[str, Any]) -> None:
        with self._lock:
            field = self._field(name)
            position = self._conn.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 FROM records WHERE collection = ?",
                (name,),
            ).fetchone()
            self._conn.execute(
                "INSERT INTO records (collection, key, body, position) VALUES (?, ?, ?, ?)",
                (name, str(record[field]), json.dumps(record), int(position[0])),
            )
            self._conn.commit()

    def replace_record(self, name: str, key: str, record: dict[str, Any]) -> bool:
        with self._lock:
            current = self.get_record(name, key)
            if current is None:
                return False
            field = self._field(name)
            stored = copy.deepcopy(record)
            stored[field] = current[field]
            self._conn.execute(
                "UPDATE records SET body = ? WHERE collection = ? AND key = ?",
                (json.dumps(stored), name, key),
            )
            self._conn.commit()
            return True

    def delete_record(self, name: str, key: str) -> bool:
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM records WHERE collection = ? AND key = ?",
                (name, key),
            )
            self._conn.commit()
            return cursor.rowcount > 0

    def get_value(self, name: str) -> Any:
        with self._lock:
            row = self._conn.execute("SELECT body FROM values_ WHERE name = ?", (name,)).fetchone()
        if row is None:
            raise KeyError(name)
        return json.loads(row[0])

    def set_value(self, name: str, value: Any) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO values_ (name, body) VALUES (?, ?) "
                "ON CONFLICT(name) DO UPDATE SET body = excluded.body",
                (name, json.dumps(value)),
            )
            self._conn.commit()

    def snapshot(self) -> dict[str, Any]:
        body: dict[str, Any] = {}
        with self._lock:
            names = {
                row[0]
                for row in self._conn.execute("SELECT DISTINCT collection FROM records").fetchall()
            }
            for name in self._collection_names():
                names.add(name)
            for name in names:
                body[name] = self.list_records(name)
            for row in self._conn.execute("SELECT name, body FROM values_").fetchall():
                body[row[0]] = json.loads(row[1])
        return body

    def _write_initial(self) -> None:
        for collection in self._initial.collections:
            for position, record in enumerate(collection.records):
                self._conn.execute(
                    "INSERT INTO records (collection, key, body, position) VALUES (?, ?, ?, ?)",
                    (collection.name, str(record[collection.key]), json.dumps(record), position),
                )
        for item in self._initial.values:
            self._conn.execute(
                "INSERT INTO values_ (name, body) VALUES (?, ?)",
                (item.name, json.dumps(item.value)),
            )

    def _field(self, name: str) -> str:
        for collection in self._initial.collections:
            if collection.name == name:
                return collection.key
        raise KeyError(name)

    def _collection_names(self) -> list[str]:
        return [item.name for item in self._initial.collections]
