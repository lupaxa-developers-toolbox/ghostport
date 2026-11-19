"""Bounded request history. A storage failure must not block the response."""

from __future__ import annotations

import json
import threading
from collections import deque
from dataclasses import dataclass
from typing import Any

from lupaxa.ghostport.config.models import HistoryConfig

SENSITIVE_HEADERS = frozenset(
    {"authorization", "cookie", "set-cookie", "x-api-key", "proxy-authorization"}
)


@dataclass(frozen=True)
class HistoryEntry:
    request_id: str
    timestamp: str
    method: str
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]
    body: str | None
    body_truncated: bool
    route: str | None
    scenario: str
    status: int
    duration_ms: float
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "method": self.method,
            "path": self.path,
            "query": self.query,
            "headers": self.headers,
            "body": self.body,
            "body_truncated": self.body_truncated,
            "route": self.route,
            "scenario": self.scenario,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


class HistoryLog:
    def __init__(self, config: HistoryConfig) -> None:
        self.config = config
        self._entries: deque[HistoryEntry] = deque(maxlen=config.max_entries)
        self._lock = threading.Lock()

    def add(self, entry: HistoryEntry) -> None:
        if not self.config.enabled:
            return
        with self._lock:
            self._entries.append(entry)

    def list_entries(self) -> list[HistoryEntry]:
        with self._lock:
            return list(self._entries)

    def get(self, request_id: str) -> HistoryEntry | None:
        with self._lock:
            for entry in self._entries:
                if entry.request_id == request_id:
                    return entry
        return None

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        key: "[redacted]" if key.casefold() in SENSITIVE_HEADERS else value
        for key, value in headers.items()
    }


def capture_body(raw: bytes, config: HistoryConfig) -> tuple[str | None, bool]:
    if not config.capture_bodies:
        return None, False
    truncated = len(raw) > config.max_body_bytes
    text = raw[: config.max_body_bytes].decode("utf-8", errors="replace")
    if not config.redact_fields:
        return text, truncated
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return text, truncated
    hidden = {name.casefold() for name in config.redact_fields}
    rendered = json.dumps(_redact(parsed, hidden), ensure_ascii=False)
    if len(rendered.encode()) > config.max_body_bytes:
        return rendered[: config.max_body_bytes], True
    return rendered, truncated


def _redact(value: Any, hidden: set[str]) -> Any:
    if isinstance(value, dict):
        return {
            key: "[redacted]" if str(key).casefold() in hidden else _redact(item, hidden)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item, hidden) for item in value]
    return value
