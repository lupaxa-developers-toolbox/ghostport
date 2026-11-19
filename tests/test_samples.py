"""The published samples stay runnable."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from lupaxa.ghostport import load_project
from lupaxa.ghostport.engine.api import ApiEngine, Incoming

ROOT = Path(__file__).resolve().parents[1] / "samples"


def _engine(tmp_path: Path, name: str) -> ApiEngine:
    destination = tmp_path / name
    shutil.copytree(ROOT / name, destination)
    return ApiEngine(load_project(destination))


def _call(
    engine: ApiEngine,
    method: str,
    path: str,
    body: bytes = b"",
    headers: dict[str, str] | None = None,
) -> Incoming:
    return Incoming(method, path, {}, headers or {}, body)


def _json(engine: ApiEngine, method: str, path: str, body: bytes = b"", headers=None):
    response = engine.handle(_call(engine, method, path, body, headers))
    payload = json.loads(response.body) if response.body else None
    return response.status, payload


def test_hello_api(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "hello-api")
    status, health = _json(engine, "GET", "/health")
    assert status == 200
    assert health == {"status": "healthy"}
    status, user = _json(engine, "GET", "/users/7")
    assert status == 200
    assert user == {"id": 7, "name": "Ada"}


def test_task_board(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "task-board")
    status, board = _json(engine, "GET", "/board")
    assert status == 200
    assert board == {"open": True}
    created = b'{"id": "2", "title": "Review samples", "done": false}'
    status, task = _json(
        engine,
        "POST",
        "/tasks",
        created,
        {"Content-Type": "application/json"},
    )
    assert status == 201
    assert task["title"] == "Review samples"
    status, listed = _json(engine, "GET", "/tasks")
    assert [item["id"] for item in listed] == ["1", "2"]
    engine.set_scenario("closed")
    status, closed = _json(engine, "GET", "/tasks")
    assert status == 503
    assert closed == {"error": "closed"}
    engine.reset_scenario()
    status, updated = _json(
        engine,
        "PATCH",
        "/tasks/2",
        b'{"done": true}',
        {"Content-Type": "application/json"},
    )
    assert status == 200
    assert updated["done"] is True
    assert updated["title"] == "Review samples"


def test_checkout(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "checkout")
    status, catalogue = _json(engine, "GET", "/catalogue")
    assert status == 200
    assert catalogue["items"][0]["sku"] == "mug"
    headers = {"Content-Type": "application/json", "x-shop": "demo"}
    status, first = _json(engine, "POST", "/payments", b"{}", headers)
    status_ok, second = _json(engine, "POST", "/payments", b"{}", headers)
    status_done, third = _json(engine, "POST", "/payments", b"{}", headers)
    assert (status, first) == (503, {"error": "busy"})
    assert (status_ok, second) == (200, {"paid": True})
    assert (status_done, third) == (410, {"error": "Sequence exhausted"})
    missing, _ = _json(engine, "POST", "/payments", b"{}", {"Content-Type": "application/json"})
    assert missing == 404
    audit_status, _ = _json(
        engine,
        "POST",
        "/audit",
        b'{"id": "9", "card": "4242"}',
        {"Content-Type": "application/json"},
    )
    assert audit_status == 503
    assert engine.store.list_records("audits") == []
    status, orders = _json(
        engine,
        "POST",
        "/orders",
        b'{"id": "101", "sku": "poster", "qty": 2}',
        {"Content-Type": "application/json"},
    )
    assert status == 201
    reloaded = ApiEngine(load_project(tmp_path / "checkout"))
    assert any(item["id"] == "101" for item in reloaded.store.list_records("orders"))
