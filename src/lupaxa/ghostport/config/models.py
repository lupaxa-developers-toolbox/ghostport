"""Immutable configuration objects produced by the loader."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _public(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [_public(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _public(item) for key, item in value.items()}
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


@dataclass(frozen=True)
class ApiIdentity:
    name: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description}


@dataclass(frozen=True)
class CorsConfig:
    enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"enabled": self.enabled}


@dataclass(frozen=True)
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8080
    request_timeout: float = 30
    max_request_body: int = 1_048_576
    cors: CorsConfig = field(default_factory=CorsConfig)

    def to_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "request_timeout": self.request_timeout,
            "max_request_body": self.max_request_body,
            "cors": self.cors.to_dict(),
        }


@dataclass(frozen=True)
class MatchDef:
    query: tuple[tuple[str, str], ...] = ()
    query_present: tuple[str, ...] = ()
    headers: tuple[tuple[str, str], ...] = ()
    headers_present: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if self.query:
            body["query"] = dict(self.query)
        if self.query_present:
            body["query_present"] = list(self.query_present)
        if self.headers:
            body["headers"] = dict(self.headers)
        if self.headers_present:
            body["headers_present"] = list(self.headers_present)
        return body


@dataclass(frozen=True)
class ResponseDef:
    status: int
    headers: tuple[tuple[str, str], ...] = ()
    json_body: Any = None
    text: str | None = None
    file: str | None = None
    template: bool = False
    has_json: bool = False

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {"status": self.status}
        if self.headers:
            body["headers"] = dict(self.headers)
        if self.has_json:
            body["json"] = self.json_body
        if self.text is not None:
            body["text"] = self.text
        if self.file is not None:
            body["file"] = self.file
            body["template"] = self.template
        return body


@dataclass(frozen=True)
class ActionDef:
    type: str
    resource: str
    input: Any = None
    key: Any = None
    status: int | None = None
    merge: bool = False
    has_input: bool = False

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {"type": self.type, "resource": self.resource}
        if self.has_input:
            body["input"] = self.input
        if self.key is not None:
            body["key"] = self.key
        if self.status is not None:
            body["status"] = self.status
        if self.merge:
            body["merge"] = True
        return body


@dataclass(frozen=True)
class BehaviourDef:
    delay_ms: int | None = None
    failure_status: int | None = None

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if self.delay_ms is not None:
            body["delay_ms"] = self.delay_ms
        if self.failure_status is not None:
            body["failure_status"] = self.failure_status
        return body


@dataclass(frozen=True)
class RouteDef:
    id: str
    method: str
    path: str
    priority: int = 0
    match: MatchDef = field(default_factory=MatchDef)
    response: ResponseDef | None = None
    sequence: tuple[ResponseDef, ...] | None = None
    action: ActionDef | None = None
    behaviour: BehaviourDef = field(default_factory=BehaviourDef)
    after_sequence: str = "repeat_last"
    exhaustion: ResponseDef | None = None
    index: int = 0

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "id": self.id,
            "method": self.method,
            "path": self.path,
            "priority": self.priority,
            "after_sequence": self.after_sequence,
        }
        if self.match.to_dict():
            body["match"] = self.match.to_dict()
        if self.response is not None:
            body["response"] = self.response.to_dict()
        if self.sequence is not None:
            body["sequence"] = [item.to_dict() for item in self.sequence]
        if self.action is not None:
            body["action"] = self.action.to_dict()
        if self.behaviour.to_dict():
            body["behaviour"] = self.behaviour.to_dict()
        if self.exhaustion is not None:
            body["exhaustion"] = self.exhaustion.to_dict()
        return body


@dataclass(frozen=True)
class ScenarioOverride:
    route: str
    response: ResponseDef | None = None
    sequence: tuple[ResponseDef, ...] | None = None
    action: ActionDef | None = None
    behaviour: BehaviourDef | None = None
    after_sequence: str | None = None
    exhaustion: ResponseDef | None = None

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {"route": self.route}
        if self.response is not None:
            body["response"] = self.response.to_dict()
        if self.sequence is not None:
            body["sequence"] = [item.to_dict() for item in self.sequence]
        if self.action is not None:
            body["action"] = self.action.to_dict()
        if self.behaviour is not None and self.behaviour.to_dict():
            body["behaviour"] = self.behaviour.to_dict()
        if self.after_sequence is not None:
            body["after_sequence"] = self.after_sequence
        if self.exhaustion is not None:
            body["exhaustion"] = self.exhaustion.to_dict()
        return body


@dataclass(frozen=True)
class ScenarioDef:
    id: str
    description: str = ""
    overrides: tuple[ScenarioOverride, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "overrides": [item.to_dict() for item in self.overrides],
        }


@dataclass(frozen=True)
class CollectionDef:
    name: str
    key: str
    records: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "collection",
            "key": self.key,
            "records": [dict(record) for record in self.records],
        }


@dataclass(frozen=True)
class ValueDef:
    name: str
    value: Any

    def to_dict(self) -> dict[str, Any]:
        return {"type": "value", "value": self.value}


@dataclass(frozen=True)
class StateDef:
    collections: tuple[CollectionDef, ...] = ()
    values: tuple[ValueDef, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {}
        for collection in self.collections:
            body[collection.name] = collection.to_dict()
        for item in self.values:
            body[item.name] = item.to_dict()
        return body


@dataclass(frozen=True)
class HistoryConfig:
    enabled: bool = True
    max_entries: int = 1000
    capture_bodies: bool = True
    max_body_bytes: int = 65536
    redact_fields: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "max_entries": self.max_entries,
            "capture_bodies": self.capture_bodies,
            "max_body_bytes": self.max_body_bytes,
            "redact_fields": list(self.redact_fields),
        }


@dataclass(frozen=True)
class RuntimeBehaviour:
    default_delay_ms: int = 0
    random_seed: int | None = None

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {"default_delay_ms": self.default_delay_ms}
        if self.random_seed is not None:
            body["random_seed"] = self.random_seed
        return body


@dataclass(frozen=True)
class StateRuntime:
    persistence: str = "memory"
    path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {"persistence": self.persistence}
        if self.path is not None:
            body["path"] = self.path
        return body


@dataclass(frozen=True)
class RuntimeConfig:
    scenario: str = "normal"
    state: StateRuntime = field(default_factory=StateRuntime)
    history: HistoryConfig = field(default_factory=HistoryConfig)
    unmatched: ResponseDef = field(
        default_factory=lambda: ResponseDef(
            status=404,
            json_body={"error": "Not Found"},
            has_json=True,
        )
    )
    behaviour: RuntimeBehaviour = field(default_factory=RuntimeBehaviour)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "state": self.state.to_dict(),
            "history": self.history.to_dict(),
            "unmatched": self.unmatched.to_dict(),
            "behaviour": self.behaviour.to_dict(),
        }


@dataclass(frozen=True)
class ManagementConfig:
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8081

    def to_dict(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "host": self.host, "port": self.port}


@dataclass(frozen=True)
class ResolvedProject:
    """One API definition after includes, defaults, and validation."""

    version: int
    api: ApiIdentity
    server: ServerConfig
    routes: tuple[RouteDef, ...]
    scenarios: tuple[ScenarioDef, ...]
    state: StateDef
    runtime: RuntimeConfig
    management: ManagementConfig
    project_root: Path
    fixtures: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "api": self.api.to_dict(),
            "server": self.server.to_dict(),
            "routes": [route.to_dict() for route in self.routes],
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
            "state": self.state.to_dict(),
            "runtime": self.runtime.to_dict(),
            "management": self.management.to_dict(),
            "fixtures": list(self.fixtures),
        }


def as_public(value: Any) -> Any:
    """Return a JSON-ready copy of a config object."""
    return _public(value)
