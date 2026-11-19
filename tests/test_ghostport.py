"""Loader, engine, state, and CLI behaviour."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import urlopen

from lupaxa.ghostport import load_project
from lupaxa.ghostport.cli import main
from lupaxa.ghostport.client import request_json
from lupaxa.ghostport.engine.api import ApiEngine, Incoming
from lupaxa.ghostport.errors import ConfigError
from lupaxa.ghostport.server import start_servers
from lupaxa.ghostport.template import render

_API = """
version: 1
api:
  name: example-api
  description: Example
routes:
  - id: health
    method: GET
    path: /health
    response:
      status: 200
      json:
        status: healthy
  - id: user
    method: GET
    path: /users/{id}
    response:
      status: 200
      json:
        id: "{{ path.id | int }}"
        name: "{{ path.id }}"
"""


def _write(directory: Path, name: str, text: str) -> Path:
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _call(
    engine: ApiEngine,
    method: str,
    path: str,
    body: bytes = b"",
    headers: dict[str, str] | None = None,
):
    return engine.handle(Incoming(method, path, {}, headers or {}, body))


def test_single_file_and_templates(tmp_path: Path) -> None:
    project = load_project(_write(tmp_path, "ghostport.yml", _API))
    engine = ApiEngine(project)
    health = json.loads(_call(engine, "GET", "/health").body)
    user = json.loads(_call(engine, "GET", "/users/7").body)
    assert health == {"status": "healthy"}
    assert user == {"id": 7, "name": "7"}
    assert isinstance(user["id"], int)


def test_directory_includes_preserve_order(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "ghostport.yml",
        """
version: 1
api:
  name: demo
include:
  routes:
    - routes/a.yml
    - routes/b.yml
""",
    )
    _write(
        tmp_path,
        "routes/a.yml",
        """
routes:
  - id: first
    method: GET
    path: /first
    response:
      status: 200
      text: one
""",
    )
    _write(
        tmp_path,
        "routes/b.yml",
        """
routes:
  - id: second
    method: GET
    path: /second
    response:
      status: 200
      text: two
""",
    )
    project = load_project(tmp_path)
    assert [route.id for route in project.routes] == ["first", "second"]


def test_validation_reports_several_problems(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "ghostport.yml",
        """
version: 1
api:
  name: bad/name
mystery: true
include:
  routes:
    - missing.yml
    - routes/*.yml
routes:
  - id: same
    method: GET
    path: /item
    response:
      status: 200
      text: a
  - id: same
    method: GET
    path: /item
    response:
      status: 200
      text: b
""",
    )
    try:
        load_project(path)
    except ConfigError as exc:
        text = "\n".join(exc.messages)
    else:
        raise AssertionError("invalid project was accepted")
    assert "unknown key" in text
    assert "missing file" in text
    assert "glob" in text
    assert "Duplicate route id" in text
    assert "must not contain" in text


def test_fixture_cannot_escape(tmp_path: Path) -> None:
    _write(tmp_path, "secret.txt", "nope")
    path = _write(
        tmp_path,
        "project/ghostport.yml",
        """
version: 1
api:
  name: demo
routes:
  - id: leak
    method: GET
    path: /leak
    response:
      status: 200
      file: ../secret.txt
""",
    )
    try:
        load_project(path)
    except ConfigError as exc:
        assert any("escapes" in message for message in exc.messages)
    else:
        raise AssertionError("path escape was accepted")


def test_template_default_and_rejection() -> None:
    assert render("{{ path.missing | default(4) }}", {"path": {}}) == 4
    try:
        render("{{ path.missing }}", {"path": {}})
    except Exception as exc:
        assert "Missing" in str(exc)
    else:
        raise AssertionError("missing value was rendered")


def test_state_scenario_and_sequence(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "ghostport.yml",
        """
version: 1
api:
  name: shop
state:
  users:
    - id: 1
      name: Alice
scenarios:
  - id: normal
    description: Normal API behaviour
  - id: closed
    description: Closed
    overrides:
      - route: list-users
        response:
          status: 503
          json:
            error: closed
routes:
  - id: list-users
    method: GET
    path: /users
    action:
      type: collection.list
      resource: users
  - id: create-user
    method: POST
    path: /users
    action:
      type: collection.create
      resource: users
      input: "{{ body }}"
  - id: flaky
    method: GET
    path: /flaky
    after_sequence: loop
    sequence:
      - status: 503
        text: "no"
      - status: 200
        text: "yes"
runtime:
  scenario: normal
""",
    )
    engine = ApiEngine(load_project(path))
    created = engine.handle(
        Incoming(
            "POST",
            "/users",
            {},
            {"Content-Type": "application/json"},
            b'{"id": 2, "name": "Bob"}',
        )
    )
    assert created.status == 201
    engine.set_scenario("closed")
    closed = json.loads(_call(engine, "GET", "/users").body)
    assert closed == {"error": "closed"}
    engine.reset_scenario()
    listed = json.loads(_call(engine, "GET", "/users").body)
    assert [item["name"] for item in listed] == ["Alice", "Bob"]
    assert _call(engine, "GET", "/flaky").body == b"no"
    assert _call(engine, "GET", "/flaky").body == b"yes"
    assert _call(engine, "GET", "/flaky").body == b"no"
    engine.reset_sequence("flaky")
    assert _call(engine, "GET", "/flaky").body == b"no"


def test_sqlite_state_survives_a_new_engine(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "ghostport.yml",
        """
version: 1
api:
  name: shop
state:
  users:
    type: collection
    key: id
    records: []
routes:
  - id: create-user
    method: POST
    path: /users
    action:
      type: collection.create
      resource: users
      input: "{{ body }}"
runtime:
  state:
    persistence: sqlite
    path: .ghostport/state.sqlite
""",
    )
    first = ApiEngine(load_project(path))
    first.handle(
        Incoming(
            "POST",
            "/users",
            {},
            {"Content-Type": "application/json"},
            b'{"id": "a", "name": "Ada"}',
        )
    )
    second = ApiEngine(load_project(path))
    assert second.store.list_records("users")[0]["name"] == "Ada"
    second.reset_state()
    assert second.store.list_records("users") == []


def test_history_redacts_and_ignores_storage_failure(tmp_path: Path) -> None:
    project = load_project(_write(tmp_path, "ghostport.yml", _API))
    engine = ApiEngine(project)
    response = engine.handle(Incoming("GET", "/health", {}, {"Authorization": "secret"}, b""))
    assert response.status == 200
    stored = engine.history.list_entries()[0]
    assert stored.headers["Authorization"] == "[redacted]"

    def fail(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("disk")

    engine.history.add = fail  # type: ignore[method-assign]
    assert _call(engine, "GET", "/health").status == 200


def test_http_and_management(tmp_path: Path) -> None:
    path = _write(tmp_path, "ghostport.yml", _API)
    api, management = start_servers(load_project(path), port=0, management_port=0)
    assert management is not None
    try:
        with urlopen(f"http://127.0.0.1:{api.server_address[1]}/health") as response:
            assert response.status == 200
            assert json.loads(response.read())["status"] == "healthy"
        base = f"http://127.0.0.1:{management.server_address[1]}"
        assert request_json(f"{base}/status")["api"] == "example-api"
        assert main(["scenario", "list", "--url", base]) == 0
    finally:
        api.shutdown()
        management.shutdown()


def test_cli_init_and_validate(tmp_path: Path, capsys) -> None:
    destination = tmp_path / "demo"
    assert main(["init", str(destination)]) == 0
    assert (destination / "routes" / "example.yml").is_file()
    assert main(["validate", str(destination)]) == 0
    captured = capsys.readouterr()
    assert "Validation successful." in captured.out
    assert main(["init", str(destination)]) == 2


def test_unmatched_and_head(tmp_path: Path) -> None:
    project = load_project(_write(tmp_path, "ghostport.yml", _API))
    engine = ApiEngine(project)
    missing = _call(engine, "GET", "/missing")
    assert missing.status == 404
    assert json.loads(missing.body) == {"error": "Not Found"}
    project = load_project(
        _write(
            tmp_path,
            "head.yml",
            """
version: 1
api:
  name: demo
routes:
  - id: ping
    method: HEAD
    path: /ping
    response:
      status: 200
      text: hidden
""",
        )
    )
    head = _call(ApiEngine(project), "HEAD", "/ping")
    assert head.status == 200
    assert head.body == b""
