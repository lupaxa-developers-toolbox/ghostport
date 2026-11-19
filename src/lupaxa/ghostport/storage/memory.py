"""Process-local state. The initial definition is never mutated."""

from __future__ import annotations

import copy
import threading
from typing import Any

from lupaxa.ghostport.config.models import StateDef


class MemoryStore:
    """Collections and values kept in memory for one engine instance."""

    def __init__(self, state: StateDef) -> None:
        self._initial = state
        self._lock = threading.RLock()
        self._collections: dict[str, dict[str, Any]] = {}
        self._values: dict[str, Any] = {}
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._collections = {
                item.name: {
                    "key": item.key,
                    "records": [copy.deepcopy(record) for record in item.records],
                }
                for item in self._initial.collections
            }
            self._values = {item.name: copy.deepcopy(item.value) for item in self._initial.values}

    def list_records(self, name: str) -> list[dict[str, Any]]:
        with self._lock:
            return [copy.deepcopy(record) for record in self._collections[name]["records"]]

    def get_record(self, name: str, key: str) -> dict[str, Any] | None:
        with self._lock:
            for record in self._collections[name]["records"]:
                if str(record[self._collections[name]["key"]]) == key:
                    return copy.deepcopy(record)
        return None

    def create_record(self, name: str, record: dict[str, Any]) -> None:
        with self._lock:
            self._collections[name]["records"].append(copy.deepcopy(record))

    def replace_record(self, name: str, key: str, record: dict[str, Any]) -> bool:
        with self._lock:
            records = self._collections[name]["records"]
            field = self._collections[name]["key"]
            for index, current in enumerate(records):
                if str(current[field]) == key:
                    stored = copy.deepcopy(record)
                    stored[field] = current[field]
                    records[index] = stored
                    return True
        return False

    def delete_record(self, name: str, key: str) -> bool:
        with self._lock:
            records = self._collections[name]["records"]
            field = self._collections[name]["key"]
            for index, current in enumerate(records):
                if str(current[field]) == key:
                    del records[index]
                    return True
        return False

    def get_value(self, name: str) -> Any:
        with self._lock:
            return copy.deepcopy(self._values[name])

    def set_value(self, name: str, value: Any) -> None:
        with self._lock:
            self._values[name] = copy.deepcopy(value)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            body: dict[str, Any] = {
                name: [copy.deepcopy(record) for record in item["records"]]
                for name, item in self._collections.items()
            }
            body.update({name: copy.deepcopy(value) for name, value in self._values.items()})
            return body
