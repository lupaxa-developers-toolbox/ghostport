"""One API engine. Routes, state, scenarios, and sequences stay inside it."""

from __future__ import annotations

import json
import mimetypes
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from lupaxa.ghostport.config.models import (
    ActionDef,
    ResolvedProject,
    ResponseDef,
    RouteDef,
    ScenarioDef,
)
from lupaxa.ghostport.engine.history import HistoryEntry, HistoryLog, capture_body, redact_headers
from lupaxa.ghostport.engine.router import compile_routes, match_route
from lupaxa.ghostport.errors import TemplateError, UsageError
from lupaxa.ghostport.storage import Store, open_store
from lupaxa.ghostport.template import render

_NO_BODY = set(range(100, 200)) | {204, 304}


@dataclass(frozen=True)
class Incoming:
    method: str
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class Outgoing:
    status: int
    headers: dict[str, str]
    body: bytes


class SequenceBook:
    """Per-route counters. Concurrent callers cannot share one position."""

    def __init__(self) -> None:
        self._index: dict[str, int] = {}

    def take(self, route_id: str, length: int, policy: str) -> int | None:
        current = self._index.get(route_id, 0)
        if policy == "loop":
            self._index[route_id] = current + 1
            return current % length
        if policy == "error":
            if current >= length:
                return None
            self._index[route_id] = current + 1
            return current
        self._index[route_id] = current + 1
        return min(current, length - 1)

    def reset(self, route_id: str | None = None) -> None:
        if route_id is None:
            self._index.clear()
            return
        self._index.pop(route_id, None)


class ApiEngine:
    """Execute one resolved API. This object is independent of the HTTP server."""

    def __init__(
        self,
        project: ResolvedProject,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.project = project
        self.store: Store = open_store(project)
        self.scenario_id = project.runtime.scenario
        self.sequences = SequenceBook()
        self.history = HistoryLog(project.runtime.history)
        self._routes = compile_routes(project.routes)
        self._scenarios = {scenario.id: scenario for scenario in project.scenarios}
        self._lock = threading.RLock()
        self._sleeper = sleeper

    def handle(self, incoming: Incoming) -> Outgoing:
        started = time.perf_counter()
        route_id: str | None = None
        error: str | None = None
        try:
            outgoing, route_id = self._dispatch(incoming, started)
        except TemplateError as exc:
            status = 400 if str(exc).startswith("Request body") else 500
            outgoing = json_response(status, {"error": str(exc)})
            error = str(exc)
        except Exception as exc:
            outgoing = json_response(500, {"error": "Internal error"})
            error = exc.__class__.__name__
        self._remember(incoming, outgoing, route_id, started, error)
        return outgoing

    def set_scenario(self, scenario_id: str) -> None:
        known = set(self._scenarios) | {self.project.runtime.scenario, "normal"}
        if scenario_id not in known:
            raise UsageError(f"Unknown scenario {scenario_id!r}.")
        with self._lock:
            self.scenario_id = scenario_id

    def reset_scenario(self) -> None:
        with self._lock:
            self.scenario_id = self.project.runtime.scenario

    def reset_state(self) -> None:
        with self._lock:
            self.store.reset()
            self.sequences.reset(None)

    def reset_sequence(self, route_id: str | None = None) -> None:
        if route_id is not None and route_id not in {route.id for route in self.project.routes}:
            raise UsageError(f"Unknown route {route_id!r}.")
        with self._lock:
            self.sequences.reset(route_id)

    def status(self) -> dict[str, Any]:
        return {
            "api": self.project.api.name,
            "description": self.project.api.description,
            "scenario": self.scenario_id,
            "scenarios": [scenario.id for scenario in self.project.scenarios],
            "routes": len(self.project.routes),
            "persistence": self.project.runtime.state.persistence,
            "history": len(self.history.list_entries()),
        }

    def _dispatch(self, incoming: Incoming, started: float) -> tuple[Outgoing, str | None]:
        if len(incoming.body) > self.project.server.max_request_body:
            return json_response(413, {"error": "Payload too large"}), None
        found = match_route(
            self._routes,
            incoming.method,
            incoming.path,
            incoming.query,
            incoming.headers,
        )
        if found is None:
            if incoming.method.upper() == "OPTIONS" and self.project.server.cors.enabled:
                return _finish(Outgoing(204, {}, b""), "OPTIONS", True), None
            context = self._context(incoming, {})
            return self._from_response(self.project.runtime.unmatched, context, True), None
        route, params = found
        with self._lock:
            effective = self._effective(route)
            delay_ms = effective.behaviour.delay_ms
        if delay_ms is None:
            delay_ms = self.project.runtime.behaviour.default_delay_ms
        if delay_ms > 0:
            self._sleeper(delay_ms / 1000)
        if time.perf_counter() - started > self.project.server.request_timeout:
            return json_response(504, {"error": "Timeout"}), route.id
        with self._lock:
            effective = self._effective(route)
            if effective.behaviour.failure_status is not None:
                outgoing = json_response(
                    effective.behaviour.failure_status,
                    {"error": "Simulated failure"},
                )
            elif effective.sequence is not None:
                outgoing = self._sequence(effective, incoming, params)
            elif effective.action is not None:
                outgoing = self._action(effective.action, self._context(incoming, params))
            elif effective.response is not None:
                outgoing = self._from_response(
                    effective.response,
                    self._context(incoming, params),
                    True,
                )
            else:
                outgoing = json_response(500, {"error": "Route has no response."})
        outgoing = _finish(outgoing, incoming.method, self.project.server.cors.enabled)
        return outgoing, route.id

    def _effective(self, route: RouteDef) -> RouteDef:
        scenario: ScenarioDef | None = self._scenarios.get(self.scenario_id)
        if scenario is None:
            return route
        override = next((item for item in scenario.overrides if item.route == route.id), None)
        if override is None:
            return route
        return replace(
            route,
            response=override.response,
            sequence=override.sequence,
            action=override.action,
            behaviour=override.behaviour or route.behaviour,
            after_sequence=override.after_sequence or route.after_sequence,
            exhaustion=override.exhaustion or route.exhaustion,
        )

    def _sequence(self, route: RouteDef, incoming: Incoming, params: dict[str, str]) -> Outgoing:
        assert route.sequence is not None
        chosen = self.sequences.take(route.id, len(route.sequence), route.after_sequence)
        if chosen is None:
            exhaustion = route.exhaustion or ResponseDef(
                status=410,
                json_body={"error": "Sequence exhausted"},
                has_json=True,
            )
            return self._from_response(exhaustion, self._context(incoming, params), True)
        return self._from_response(route.sequence[chosen], self._context(incoming, params), True)

    def _action(self, action: ActionDef, context: dict[str, Any]) -> Outgoing:
        key = render(action.key, context) if action.key is not None else None
        payload = render(action.input, context) if action.has_input else None
        if action.type == "collection.list":
            return json_response(action.status or 200, self.store.list_records(action.resource))
        if action.type == "collection.get":
            record = self.store.get_record(action.resource, _identity(key))
            if record is None:
                return json_response(404, {"error": "Not Found"})
            return json_response(action.status or 200, record)
        if action.type == "collection.create":
            return self._create(action, payload)
        if action.type == "collection.update":
            return self._update(action, key, payload)
        if action.type == "collection.delete":
            removed = self.store.delete_record(action.resource, _identity(key))
            if not removed:
                return json_response(404, {"error": "Not Found"})
            return Outgoing(action.status or 204, {}, b"")
        if action.type == "state.get":
            return json_response(action.status or 200, self.store.get_value(action.resource))
        self.store.set_value(action.resource, payload)
        return json_response(action.status or 200, {"updated": action.resource})

    def _create(self, action: ActionDef, payload: Any) -> Outgoing:
        if not isinstance(payload, dict):
            return json_response(400, {"error": "Input must be an object."})
        field = _collection_key(self.project, action.resource)
        if field not in payload:
            return json_response(400, {"error": f"Missing {field}."})
        identity = str(payload[field])
        if self.store.get_record(action.resource, identity) is not None:
            return json_response(409, {"error": "Already exists."})
        self.store.create_record(action.resource, payload)
        return json_response(action.status or 201, payload)

    def _update(self, action: ActionDef, key: Any, payload: Any) -> Outgoing:
        if not isinstance(payload, dict):
            return json_response(400, {"error": "Input must be an object."})
        field = _collection_key(self.project, action.resource)
        identity = _identity(key) if key is not None else str(payload.get(field, ""))
        current = self.store.get_record(action.resource, identity)
        if current is None:
            return json_response(404, {"error": "Not Found"})
        stored = {**current, **payload} if action.merge else payload
        self.store.replace_record(action.resource, identity, stored)
        saved = self.store.get_record(action.resource, identity)
        return json_response(action.status or 200, saved if saved is not None else stored)

    def _from_response(
        self,
        response: ResponseDef,
        context: dict[str, Any],
        allow_template: bool,
    ) -> Outgoing:
        headers = dict(response.headers)
        if response.file is not None:
            body, content_type = _file_body(
                self.project.project_root,
                response,
                context,
                allow_template,
            )
            headers.setdefault("Content-Type", content_type)
            return Outgoing(response.status, headers, body)
        if response.has_json:
            rendered = render(response.json_body, context)
            headers.setdefault("Content-Type", "application/json; charset=utf-8")
            return Outgoing(response.status, headers, _dump(rendered))
        if response.text is not None:
            rendered = render(response.text, context)
            text = rendered if isinstance(rendered, str) else json.dumps(rendered)
            headers.setdefault("Content-Type", "text/plain; charset=utf-8")
            return Outgoing(response.status, headers, text.encode())
        return Outgoing(response.status, headers, b"")

    def _context(self, incoming: Incoming, params: dict[str, str]) -> dict[str, Any]:
        scenario = self._scenarios.get(self.scenario_id)
        return {
            "path": params,
            "query": {
                key: values[0] if len(values) == 1 else values
                for key, values in incoming.query.items()
            },
            "headers": dict(incoming.headers),
            "body": _body_value(incoming),
            "state": self.store.snapshot(),
            "scenario": {
                "id": self.scenario_id,
                "description": "" if scenario is None else scenario.description,
            },
        }

    def _remember(
        self,
        incoming: Incoming,
        outgoing: Outgoing,
        route_id: str | None,
        started: float,
        error: str | None,
    ) -> None:
        try:
            body, truncated = capture_body(incoming.body, self.project.runtime.history)
            self.history.add(
                HistoryEntry(
                    request_id=uuid.uuid4().hex,
                    timestamp=datetime.now(UTC).isoformat(),
                    method=incoming.method.upper(),
                    path=incoming.path,
                    query=incoming.query,
                    headers=redact_headers(incoming.headers),
                    body=body,
                    body_truncated=truncated,
                    route=route_id,
                    scenario=self.scenario_id,
                    status=outgoing.status,
                    duration_ms=round((time.perf_counter() - started) * 1000, 3),
                    error=error,
                )
            )
        except Exception:
            return


def json_response(status: int, payload: Any) -> Outgoing:
    return Outgoing(status, {"Content-Type": "application/json; charset=utf-8"}, _dump(payload))


def _dump(payload: Any) -> bytes:
    try:
        return json.dumps(payload, ensure_ascii=False).encode()
    except TypeError as exc:
        raise TemplateError("Response JSON is not serialisable.") from exc


def _finish(outgoing: Outgoing, method: str, cors: bool) -> Outgoing:
    headers = dict(outgoing.headers)
    body = outgoing.body
    if method.upper() == "HEAD" or outgoing.status in _NO_BODY:
        body = b""
    if cors:
        headers.setdefault("Access-Control-Allow-Origin", "*")
        headers.setdefault(
            "Access-Control-Allow-Methods",
            "GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS",
        )
        headers.setdefault("Access-Control-Allow-Headers", "*")
    headers["Content-Length"] = str(len(body))
    return Outgoing(outgoing.status, headers, body)


def _file_body(
    root: Any,
    response: ResponseDef,
    context: dict[str, Any],
    allow_template: bool,
) -> tuple[bytes, str]:
    assert response.file is not None
    path = (root / response.file).resolve()
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if response.template and allow_template:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            rendered = render(json.loads(text), context)
            return _dump(rendered), "application/json; charset=utf-8"
        rendered = render(text, context)
        output = rendered if isinstance(rendered, str) else json.dumps(rendered, ensure_ascii=False)
        if not content_type.startswith("text/") and content_type != "application/json":
            content_type = "text/plain; charset=utf-8"
        return output.encode(), content_type
    return path.read_bytes(), content_type


def _body_value(incoming: Incoming) -> Any:
    if not incoming.body:
        return None
    content_type = ""
    for key, value in incoming.headers.items():
        if key.casefold() == "content-type":
            content_type = value
            break
    if "json" not in content_type.casefold():
        return incoming.body.decode("utf-8", errors="replace")
    try:
        return json.loads(incoming.body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise TemplateError("Request body is not valid JSON.") from exc


def _identity(value: Any) -> str:
    if isinstance(value, bool) or value is None or isinstance(value, (dict, list)):
        raise TemplateError("Record key must be a string or number.")
    return str(value)


def _collection_key(project: ResolvedProject, name: str) -> str:
    for collection in project.state.collections:
        if collection.name == name:
            return collection.key
    raise TemplateError(f"Unknown collection {name!r}.")
