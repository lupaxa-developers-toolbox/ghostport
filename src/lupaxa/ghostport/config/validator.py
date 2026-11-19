"""Schema checks for Ghost Port documents. Unknown keys are errors."""

from __future__ import annotations

import copy
from typing import Any, TypeGuard

from lupaxa.ghostport.config.models import (
    ActionDef,
    ApiIdentity,
    BehaviourDef,
    CollectionDef,
    CorsConfig,
    HistoryConfig,
    ManagementConfig,
    MatchDef,
    ResponseDef,
    RouteDef,
    RuntimeBehaviour,
    RuntimeConfig,
    ScenarioDef,
    ScenarioOverride,
    ServerConfig,
    StateRuntime,
    ValueDef,
)

METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
ACTIONS = {
    "collection.list",
    "collection.get",
    "collection.create",
    "collection.update",
    "collection.delete",
    "state.get",
    "state.set",
}
POLICIES = {"repeat_last", "loop", "error"}
LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def is_int(value: Any) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def unknown(raw: dict[str, Any], allowed: set[str], where: str, errors: list[str]) -> None:
    for key in raw:
        if key not in allowed:
            errors.append(f"{where}: unknown key {key!r}.")


def parse_response(raw: Any, where: str, errors: list[str]) -> ResponseDef | None:
    if not isinstance(raw, dict):
        errors.append(f"{where}: response must be a mapping.")
        return None
    unknown(raw, {"status", "headers", "json", "text", "file", "template"}, where, errors)
    status = raw.get("status", 200)
    if not is_int(status) or not 100 <= status <= 599:
        errors.append(f"{where}: status must be an integer from 100 to 599.")
        status = 500
    sources = [name for name in ("json", "text", "file") if name in raw]
    if len(sources) > 1:
        errors.append(f"{where}: use only one of json, text, or file.")
    text = raw.get("text") if "text" in raw else None
    if "text" in raw and not isinstance(text, str):
        errors.append(f"{where}: text must be a string.")
        text = None
    file_name = raw.get("file") if "file" in raw else None
    if "file" in raw and not isinstance(file_name, str):
        errors.append(f"{where}: file must be a path.")
        file_name = None
    template = raw.get("template", False)
    if not isinstance(template, bool):
        errors.append(f"{where}: template must be true or false.")
        template = False
    if template and "file" not in raw:
        errors.append(f"{where}: template is only valid on a file response.")
    headers = _headers(raw.get("headers", {}), f"{where}.headers", errors)
    return ResponseDef(
        status=int(status),
        headers=headers,
        json_body=copy.deepcopy(raw.get("json")),
        text=text if isinstance(text, str) else None,
        file=file_name if isinstance(file_name, str) else None,
        template=bool(template) and isinstance(file_name, str),
        has_json="json" in raw and len(sources) == 1,
    )


def parse_action(raw: Any, where: str, errors: list[str]) -> ActionDef | None:
    if not isinstance(raw, dict):
        errors.append(f"{where}: action must be a mapping.")
        return None
    unknown(raw, {"type", "resource", "input", "key", "status", "merge"}, where, errors)
    kind = raw.get("type")
    if kind not in ACTIONS:
        errors.append(f"{where}: unknown action {kind!r}.")
        kind = "state.get"
    resource = raw.get("resource")
    if not isinstance(resource, str) or not resource.strip():
        errors.append(f"{where}: action resource must be a name.")
        resource = ""
    status = raw.get("status")
    if "status" in raw and (not is_int(status) or not 100 <= status <= 599):
        errors.append(f"{where}: action status must be an integer from 100 to 599.")
        status = None
    merge = raw.get("merge", False)
    if not isinstance(merge, bool):
        errors.append(f"{where}: merge must be true or false.")
        merge = False
    return ActionDef(
        type=str(kind),
        resource=str(resource),
        input=copy.deepcopy(raw.get("input")),
        key=copy.deepcopy(raw.get("key")) if "key" in raw else None,
        status=status if is_int(status) else None,
        merge=bool(merge),
        has_input="input" in raw,
    )


def parse_behaviour(raw: Any, where: str, errors: list[str]) -> BehaviourDef:
    if raw is None:
        return BehaviourDef()
    if not isinstance(raw, dict):
        errors.append(f"{where}: behaviour must be a mapping.")
        return BehaviourDef()
    unknown(raw, {"delay_ms", "failure_status"}, where, errors)
    delay = raw.get("delay_ms")
    if "delay_ms" in raw and (not is_int(delay) or delay < 0):
        errors.append(f"{where}: delay_ms must be a non-negative integer.")
        delay = None
    failure = raw.get("failure_status")
    if "failure_status" in raw and (not is_int(failure) or not 100 <= failure <= 599):
        errors.append(f"{where}: failure_status must be an integer from 100 to 599.")
        failure = None
    return BehaviourDef(
        delay_ms=delay if is_int(delay) else None,
        failure_status=failure if is_int(failure) else None,
    )


def parse_match(raw: Any, where: str, errors: list[str]) -> MatchDef:
    if raw is None:
        return MatchDef()
    if not isinstance(raw, dict):
        errors.append(f"{where}: match must be a mapping.")
        return MatchDef()
    unknown(raw, {"query", "headers", "query_present", "headers_present"}, where, errors)
    return MatchDef(
        query=_pairs(raw.get("query", {}), f"{where}.query", errors),
        headers=_pairs(raw.get("headers", {}), f"{where}.headers", errors),
        query_present=_names(raw.get("query_present", []), f"{where}.query_present", errors),
        headers_present=_names(raw.get("headers_present", []), f"{where}.headers_present", errors),
    )


def parse_route(raw: Any, where: str, errors: list[str], index: int) -> RouteDef | None:
    if not isinstance(raw, dict):
        errors.append(f"{where}: route must be a mapping.")
        return None
    unknown(
        raw,
        {
            "id",
            "method",
            "path",
            "priority",
            "match",
            "response",
            "sequence",
            "action",
            "behaviour",
            "after_sequence",
            "exhaustion",
        },
        where,
        errors,
    )
    route_id = raw.get("id")
    if not isinstance(route_id, str) or not route_id.strip():
        errors.append(f"{where}: route id must be a non-empty string.")
        return None
    method = raw.get("method")
    if not isinstance(method, str) or method.upper() not in METHODS:
        errors.append(f"{where}: method must be one of {', '.join(sorted(METHODS))}.")
        method = "GET"
    path = raw.get("path")
    if not isinstance(path, str) or not path.startswith("/"):
        errors.append(f"{where}: path must be a string starting with /.")
        path = "/"
    priority = raw.get("priority", 0)
    if not is_int(priority):
        errors.append(f"{where}: priority must be an integer.")
        priority = 0
    modes = [name for name in ("response", "sequence", "action") if name in raw]
    if len(modes) != 1:
        errors.append(
            f"{where}: route {route_id} needs exactly one of response, sequence, or action."
        )
    sequence = None
    if "sequence" in raw:
        sequence = _sequence(raw.get("sequence"), f"{where}.sequence", errors)
    policy = raw.get("after_sequence", "repeat_last" if sequence is not None else "repeat_last")
    if "after_sequence" in raw and sequence is None:
        errors.append(f"{where}: after_sequence belongs on a sequence route.")
    if not isinstance(policy, str) or policy not in POLICIES:
        errors.append(f"{where}: after_sequence must be repeat_last, loop, or error.")
        policy = "repeat_last"
    exhaustion = None
    if "exhaustion" in raw:
        if policy != "error":
            errors.append(f"{where}: exhaustion is used when after_sequence is error.")
        exhaustion = parse_response(raw.get("exhaustion"), f"{where}.exhaustion", errors)
    return RouteDef(
        id=route_id,
        method=str(method).upper(),
        path=str(path),
        priority=int(priority),
        match=parse_match(raw.get("match"), f"{where}.match", errors),
        response=parse_response(raw.get("response"), f"{where}.response", errors)
        if "response" in raw
        else None,
        sequence=sequence,
        action=parse_action(raw.get("action"), f"{where}.action", errors)
        if "action" in raw
        else None,
        behaviour=parse_behaviour(raw.get("behaviour"), f"{where}.behaviour", errors),
        after_sequence=policy if policy in POLICIES else "repeat_last",
        exhaustion=exhaustion,
        index=index,
    )


def parse_routes(raw: Any, where: str, errors: list[str], start: int) -> list[RouteDef]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        errors.append(f"{where}: routes must be a list.")
        return []
    routes: list[RouteDef] = []
    for offset, item in enumerate(raw):
        route = parse_route(item, f"{where}[{offset}]", errors, start + offset)
        if route is not None:
            routes.append(route)
    return routes


def parse_override(raw: Any, where: str, errors: list[str]) -> ScenarioOverride | None:
    if not isinstance(raw, dict):
        errors.append(f"{where}: override must be a mapping.")
        return None
    unknown(
        raw,
        {"route", "response", "sequence", "action", "behaviour", "after_sequence", "exhaustion"},
        where,
        errors,
    )
    route = raw.get("route")
    if not isinstance(route, str) or not route.strip():
        errors.append(f"{where}: override route must be a route id.")
        return None
    modes = [name for name in ("response", "sequence", "action") if name in raw]
    if len(modes) != 1:
        errors.append(
            f"{where}: override for {route} needs exactly one of response, sequence, or action."
        )
    sequence = (
        _sequence(raw.get("sequence"), f"{where}.sequence", errors) if "sequence" in raw else None
    )
    policy = raw.get("after_sequence")
    if policy is not None and policy not in POLICIES:
        errors.append(f"{where}: after_sequence must be repeat_last, loop, or error.")
        policy = None
    return ScenarioOverride(
        route=route,
        response=parse_response(raw.get("response"), f"{where}.response", errors)
        if "response" in raw
        else None,
        sequence=sequence,
        action=parse_action(raw.get("action"), f"{where}.action", errors)
        if "action" in raw
        else None,
        behaviour=parse_behaviour(raw.get("behaviour"), f"{where}.behaviour", errors)
        if "behaviour" in raw
        else None,
        after_sequence=policy if isinstance(policy, str) and policy in POLICIES else None,
        exhaustion=parse_response(raw.get("exhaustion"), f"{where}.exhaustion", errors)
        if "exhaustion" in raw
        else None,
    )


def parse_scenarios(raw: Any, where: str, errors: list[str]) -> list[ScenarioDef]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        errors.append(f"{where}: scenarios must be a list.")
        return []
    found: list[ScenarioDef] = []
    for offset, item in enumerate(raw):
        place = f"{where}[{offset}]"
        if not isinstance(item, dict):
            errors.append(f"{place}: scenario must be a mapping.")
            continue
        unknown(item, {"id", "description", "overrides"}, place, errors)
        scenario_id = item.get("id")
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            errors.append(f"{place}: scenario id must be a non-empty string.")
            continue
        description = item.get("description", "")
        if not isinstance(description, str):
            errors.append(f"{place}: description must be a string.")
            description = ""
        overrides: list[ScenarioOverride] = []
        raw_overrides = item.get("overrides", [])
        if not isinstance(raw_overrides, list):
            errors.append(f"{place}: overrides must be a list.")
        else:
            for index, override in enumerate(raw_overrides):
                parsed = parse_override(override, f"{place}.overrides[{index}]", errors)
                if parsed is not None:
                    overrides.append(parsed)
        found.append(ScenarioDef(scenario_id, description, tuple(overrides)))
    return found


def parse_state(
    raw: Any, where: str, errors: list[str]
) -> tuple[list[CollectionDef], list[ValueDef]]:
    if raw is None:
        return [], []
    if not isinstance(raw, dict):
        errors.append(f"{where}: state must be a mapping.")
        return [], []
    collections: list[CollectionDef] = []
    values: list[ValueDef] = []
    for name, body in raw.items():
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{where}: state names must be strings.")
            continue
        place = f"{where}.{name}"
        if isinstance(body, dict) and body.get("type") == "collection":
            collection = _collection(name, body, place, errors)
            if collection is not None:
                collections.append(collection)
            continue
        if isinstance(body, dict) and body.get("type") == "value":
            unknown(body, {"type", "value"}, place, errors)
            if "value" not in body:
                errors.append(f"{place}: value is required.")
            values.append(ValueDef(name, copy.deepcopy(body.get("value"))))
            continue
        if isinstance(body, list) and _shorthand_collection(body):
            records = tuple(copy.deepcopy(item) for item in body)
            collections.append(CollectionDef(name, "id", records))
            continue
        if isinstance(body, list) and any(isinstance(item, dict) and "id" in item for item in body):
            errors.append(f"{place}: shorthand records must all be objects with id.")
            continue
        if isinstance(body, dict) and "type" in body:
            errors.append(f"{place}: unknown state type {body.get('type')!r}.")
            continue
        values.append(ValueDef(name, copy.deepcopy(body)))
    return collections, values


def parse_server(raw: Any, errors: list[str]) -> ServerConfig:
    if raw is None:
        return ServerConfig()
    if not isinstance(raw, dict):
        errors.append("server: must be a mapping.")
        return ServerConfig()
    unknown(raw, {"host", "port", "request_timeout", "max_request_body", "cors"}, "server", errors)
    host = raw.get("host", "127.0.0.1")
    if not isinstance(host, str) or not host.strip():
        errors.append("server.host: must be a host name or address.")
        host = "127.0.0.1"
    port = raw.get("port", 8080)
    if not is_int(port) or not 0 <= int(port) <= 65535:
        errors.append("server.port: must be an integer from 0 to 65535.")
        port = 8080
    timeout = raw.get("request_timeout", 30)
    if not _positive_number(timeout):
        errors.append("server.request_timeout: must be a positive number of seconds.")
        timeout = 30
    limit = raw.get("max_request_body", 1_048_576)
    if not is_int(limit) or int(limit) < 1:
        errors.append("server.max_request_body: must be a positive integer.")
        limit = 1_048_576
    cors_raw = raw.get("cors", {})
    enabled = False
    if cors_raw is None:
        cors_raw = {}
    if not isinstance(cors_raw, dict):
        errors.append("server.cors: must be a mapping.")
    else:
        unknown(cors_raw, {"enabled"}, "server.cors", errors)
        enabled = cors_raw.get("enabled", False)
        if not isinstance(enabled, bool):
            errors.append("server.cors.enabled: must be true or false.")
            enabled = False
    return ServerConfig(str(host), int(port), float(timeout), int(limit), CorsConfig(bool(enabled)))


def parse_runtime(raw: Any, errors: list[str]) -> RuntimeConfig:
    if raw is None:
        return RuntimeConfig()
    if not isinstance(raw, dict):
        errors.append("runtime: must be a mapping.")
        return RuntimeConfig()
    unknown(raw, {"scenario", "state", "history", "unmatched", "behaviour"}, "runtime", errors)
    scenario = raw.get("scenario", "normal")
    if not isinstance(scenario, str) or not scenario.strip():
        errors.append("runtime.scenario: must be a scenario id.")
        scenario = "normal"
    unmatched = RuntimeConfig().unmatched
    if "unmatched" in raw and raw.get("unmatched") is not None:
        parsed = parse_response(raw.get("unmatched"), "runtime.unmatched", errors)
        if parsed is not None:
            unmatched = parsed
    return RuntimeConfig(
        scenario=scenario,
        state=_state_runtime(raw.get("state"), errors),
        history=_history(raw.get("history"), errors),
        unmatched=unmatched,
        behaviour=_runtime_behaviour(raw.get("behaviour"), errors),
    )


def parse_management(raw: Any, errors: list[str]) -> ManagementConfig:
    if raw is None:
        return ManagementConfig()
    if not isinstance(raw, dict):
        errors.append("management: must be a mapping.")
        return ManagementConfig()
    unknown(raw, {"enabled", "host", "port"}, "management", errors)
    enabled = raw.get("enabled", True)
    if not isinstance(enabled, bool):
        errors.append("management.enabled: must be true or false.")
        enabled = True
    host = raw.get("host", "127.0.0.1")
    if not isinstance(host, str) or host not in LOOPBACK:
        errors.append("management.host: must be 127.0.0.1, localhost, or ::1.")
        host = "127.0.0.1"
    port = raw.get("port", 8081)
    if not is_int(port) or not 0 <= int(port) <= 65535:
        errors.append("management.port: must be an integer from 0 to 65535.")
        port = 8081
    return ManagementConfig(bool(enabled), str(host), int(port))


def parse_api(raw: Any, errors: list[str]) -> ApiIdentity | None:
    if not isinstance(raw, dict):
        errors.append("api: must be a mapping.")
        return None
    unknown(raw, {"name", "description"}, "api", errors)
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("api.name: is required.")
        return None
    if any(token in name for token in ("://", "/", ":", " ")):
        errors.append("api.name: must not contain a host, port, or mount path.")
    description = raw.get("description", "")
    if not isinstance(description, str):
        errors.append("api.description: must be a string.")
        description = ""
    return ApiIdentity(name.strip(), description)


def _sequence(raw: Any, where: str, errors: list[str]) -> tuple[ResponseDef, ...] | None:
    if not isinstance(raw, list) or not raw:
        errors.append(f"{where}: sequence must be a non-empty list.")
        return ()
    items: list[ResponseDef] = []
    for index, item in enumerate(raw):
        parsed = parse_response(item, f"{where}[{index}]", errors)
        if parsed is not None:
            items.append(parsed)
    return tuple(items)


def _collection(
    name: str, body: dict[str, Any], where: str, errors: list[str]
) -> CollectionDef | None:
    unknown(body, {"type", "key", "records"}, where, errors)
    key = body.get("key")
    if not isinstance(key, str) or not key.strip():
        errors.append(f"{where}: collection key is required.")
        return None
    records = body.get("records", [])
    if not isinstance(records, list):
        errors.append(f"{where}: records must be a list.")
        return None
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict) or key not in record:
            errors.append(f"{where}: record {index} must be an object with {key!r}.")
            continue
        identity = str(record[key])
        if identity in seen:
            errors.append(f"{where}: duplicate record key {identity!r}.")
        seen.add(identity)
        cleaned.append(copy.deepcopy(record))
    return CollectionDef(name, key, tuple(cleaned))


def _shorthand_collection(body: list[Any]) -> bool:
    return bool(body) and all(isinstance(item, dict) and "id" in item for item in body)


def _headers(raw: Any, where: str, errors: list[str]) -> tuple[tuple[str, str], ...]:
    return _pairs(raw, where, errors)


def _pairs(raw: Any, where: str, errors: list[str]) -> tuple[tuple[str, str], ...]:
    if raw is None:
        return ()
    if not isinstance(raw, dict):
        errors.append(f"{where}: must be a mapping of names to values.")
        return ()
    pairs: list[tuple[str, str]] = []
    for key, value in raw.items():
        if not isinstance(key, str):
            errors.append(f"{where}: names must be strings.")
            continue
        scalar = _scalar(value, f"{where}.{key}", errors)
        if scalar is not None:
            pairs.append((key, scalar))
    return tuple(pairs)


def _names(raw: Any, where: str, errors: list[str]) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or not all(isinstance(item, str) and item for item in raw):
        errors.append(f"{where}: must be a list of names.")
        return ()
    return tuple(raw)


def _scalar(value: Any, where: str, errors: list[str]) -> str | None:
    if isinstance(value, str):
        return value
    if is_int(value):
        return str(value)
    errors.append(f"{where}: value must be a string or integer.")
    return None


def _positive_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    return isinstance(value, (int, float)) and float(value) > 0


def _state_runtime(raw: Any, errors: list[str]) -> StateRuntime:
    if raw is None:
        return StateRuntime()
    if not isinstance(raw, dict):
        errors.append("runtime.state: must be a mapping.")
        return StateRuntime()
    unknown(raw, {"persistence", "path"}, "runtime.state", errors)
    persistence = raw.get("persistence", "memory")
    if persistence not in {"memory", "sqlite"}:
        errors.append("runtime.state.persistence: must be memory or sqlite.")
        persistence = "memory"
    path = raw.get("path")
    if "path" in raw and not isinstance(path, str):
        errors.append("runtime.state.path: must be a file path.")
        path = None
    if persistence == "sqlite" and not isinstance(path, str):
        path = ".ghostport/state.sqlite"
    return StateRuntime(str(persistence), path if isinstance(path, str) else None)


def _history(raw: Any, errors: list[str]) -> HistoryConfig:
    if raw is None:
        return HistoryConfig()
    if not isinstance(raw, dict):
        errors.append("runtime.history: must be a mapping.")
        return HistoryConfig()
    unknown(
        raw,
        {"enabled", "max_entries", "capture_bodies", "max_body_bytes", "redact_fields"},
        "runtime.history",
        errors,
    )
    enabled = raw.get("enabled", True)
    capture = raw.get("capture_bodies", True)
    if not isinstance(enabled, bool):
        errors.append("runtime.history.enabled: must be true or false.")
        enabled = True
    if not isinstance(capture, bool):
        errors.append("runtime.history.capture_bodies: must be true or false.")
        capture = True
    maximum = raw.get("max_entries", 1000)
    body_limit = raw.get("max_body_bytes", 65536)
    if not is_int(maximum) or int(maximum) < 1:
        errors.append("runtime.history.max_entries: must be a positive integer.")
        maximum = 1000
    if not is_int(body_limit) or int(body_limit) < 0:
        errors.append("runtime.history.max_body_bytes: must be a non-negative integer.")
        body_limit = 65536
    fields = raw.get("redact_fields", [])
    if not isinstance(fields, list) or not all(isinstance(item, str) for item in fields):
        errors.append("runtime.history.redact_fields: must be a list of field names.")
        fields = []
    return HistoryConfig(bool(enabled), int(maximum), bool(capture), int(body_limit), tuple(fields))


def _runtime_behaviour(raw: Any, errors: list[str]) -> RuntimeBehaviour:
    if raw is None:
        return RuntimeBehaviour()
    if not isinstance(raw, dict):
        errors.append("runtime.behaviour: must be a mapping.")
        return RuntimeBehaviour()
    unknown(raw, {"default_delay_ms", "random_seed"}, "runtime.behaviour", errors)
    delay = raw.get("default_delay_ms", 0)
    if not is_int(delay) or delay < 0:
        errors.append("runtime.behaviour.default_delay_ms: must be a non-negative integer.")
        delay = 0
    seed = raw.get("random_seed")
    if "random_seed" in raw and not is_int(seed):
        errors.append("runtime.behaviour.random_seed: must be an integer.")
        seed = None
    return RuntimeBehaviour(delay, seed if is_int(seed) else None)
