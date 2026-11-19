"""Semantic checks and the immutable project object."""

from __future__ import annotations

from pathlib import Path

from lupaxa.ghostport.config.includes import inside, resolve_fixture
from lupaxa.ghostport.config.models import (
    ActionDef,
    ApiIdentity,
    ManagementConfig,
    ResolvedProject,
    ResponseDef,
    RouteDef,
    RuntimeConfig,
    ScenarioDef,
    ServerConfig,
    StateDef,
)
from lupaxa.ghostport.config.paths import compile_path, path_shape

_TEXT_SUFFIXES = {".json", ".txt", ".text", ".csv", ".xml", ".html", ".md", ".yaml", ".yml"}


def assemble(
    *,
    version: int,
    api: ApiIdentity | None,
    server: ServerConfig,
    routes: list[RouteDef],
    scenarios: list[ScenarioDef],
    state: StateDef,
    runtime: RuntimeConfig,
    management: ManagementConfig,
    root: Path,
    errors: list[str],
) -> ResolvedProject | None:
    """Check references and return the project when the definition is usable."""
    if api is None:
        errors.append("api: is required.")
    _routes(routes, errors)
    _scenarios(scenarios, routes, runtime, errors)
    _actions(routes, scenarios, state, errors)
    fixtures = _fixtures(routes, scenarios, runtime, root, server, errors)
    _state_file(root, runtime, errors)
    if not routes:
        errors.append("Project has no routes after includes were loaded.")
    if errors or api is None:
        return None
    numbered = tuple(
        RouteDef(
            id=route.id,
            method=route.method,
            path=route.path,
            priority=route.priority,
            match=route.match,
            response=route.response,
            sequence=route.sequence,
            action=route.action,
            behaviour=route.behaviour,
            after_sequence=route.after_sequence,
            exhaustion=route.exhaustion,
            index=index,
        )
        for index, route in enumerate(routes)
    )
    return ResolvedProject(
        version=version,
        api=api,
        server=server,
        routes=numbered,
        scenarios=tuple(scenarios),
        state=state,
        runtime=runtime,
        management=management,
        project_root=root,
        fixtures=tuple(fixtures),
    )


def _routes(routes: list[RouteDef], errors: list[str]) -> None:
    seen: set[str] = set()
    shapes: dict[tuple[str, str, object], str] = {}
    for route in routes:
        if route.id in seen:
            errors.append(f"Duplicate route id {route.id!r}.")
        seen.add(route.id)
        try:
            compile_path(route.path)
        except ValueError as exc:
            errors.append(f"Route {route.id}: {exc}")
        signature = (route.method, path_shape(route.path), route.match)
        previous = shapes.get(signature)
        if previous is not None:
            errors.append(
                f"Routes {previous!r} and {route.id!r} have the same method, path, and match."
            )
        else:
            shapes[signature] = route.id


def _scenarios(
    scenarios: list[ScenarioDef],
    routes: list[RouteDef],
    runtime: RuntimeConfig,
    errors: list[str],
) -> None:
    ids = {route.id for route in routes}
    seen: set[str] = set()
    for scenario in scenarios:
        if scenario.id in seen:
            errors.append(f"Duplicate scenario id {scenario.id!r}.")
        seen.add(scenario.id)
        overridden: set[str] = set()
        for override in scenario.overrides:
            if override.route in overridden:
                errors.append(
                    f"Scenario {scenario.id}: route {override.route!r} is overridden twice."
                )
            overridden.add(override.route)
            if override.route not in ids:
                errors.append(f"Scenario {scenario.id}: unknown route {override.route!r}.")
    if runtime.scenario != "normal" and runtime.scenario not in seen:
        errors.append(f"runtime.scenario: unknown scenario {runtime.scenario!r}.")


def _actions(
    routes: list[RouteDef],
    scenarios: list[ScenarioDef],
    state: StateDef,
    errors: list[str],
) -> None:
    collections = {item.name: item for item in state.collections}
    values = {item.name for item in state.values}
    names = set(collections) | values
    overlap = set(collections) & values
    for name in sorted(overlap):
        errors.append(f"State name {name!r} is declared more than once.")
    actions: list[tuple[str, ActionDef]] = []
    for route in routes:
        if route.action is not None:
            actions.append((f"Route {route.id}", route.action))
    for scenario in scenarios:
        for override in scenario.overrides:
            if override.action is not None:
                actions.append((f"Scenario {scenario.id} route {override.route}", override.action))
    for where, action in actions:
        if not action.resource:
            continue
        if action.type.startswith("collection."):
            collection = collections.get(action.resource)
            if collection is None:
                errors.append(f"{where}: collection {action.resource!r} is not defined.")
            elif action.type == "collection.create" and not action.has_input:
                errors.append(f"{where}: collection.create needs input.")
        elif action.resource not in names or action.resource in collections:
            errors.append(f"{where}: value {action.resource!r} is not defined.")


def _fixtures(
    routes: list[RouteDef],
    scenarios: list[ScenarioDef],
    runtime: RuntimeConfig,
    root: Path,
    server: ServerConfig,
    errors: list[str],
) -> list[str]:
    limit = server.max_request_body
    found: list[str] = []
    responses: list[tuple[str, ResponseDef]] = [("runtime.unmatched", runtime.unmatched)]
    for route in routes:
        responses.extend(
            _route_responses(f"Route {route.id}", route.response, route.sequence, route.exhaustion)
        )
    for scenario in scenarios:
        for override in scenario.overrides:
            label = f"Scenario {scenario.id} route {override.route}"
            responses.extend(
                _route_responses(label, override.response, override.sequence, override.exhaustion)
            )
    for where, response in responses:
        if response.file is None:
            continue
        path = resolve_fixture(root, response.file, f"{where} file", errors)
        if path is None:
            continue
        found.append(response.file)
        size = path.stat().st_size
        if size > limit:
            errors.append(
                f"{where}: fixture {response.file} is larger than max_request_body ({limit})."
            )
        if response.template:
            _check_template_file(path, response.file, where, errors)
    return found


def _route_responses(
    where: str,
    response: ResponseDef | None,
    sequence: tuple[ResponseDef, ...] | None,
    exhaustion: ResponseDef | None,
) -> list[tuple[str, ResponseDef]]:
    found: list[tuple[str, ResponseDef]] = []
    if response is not None:
        found.append((where, response))
    if sequence is not None:
        found.extend((f"{where} sequence", item) for item in sequence)
    if exhaustion is not None:
        found.append((f"{where} exhaustion", exhaustion))
    return found


def _state_file(root: Path, runtime: RuntimeConfig, errors: list[str]) -> None:
    raw = runtime.state.path
    if raw is None:
        return
    candidate = Path(raw)
    if candidate.is_absolute() or not inside(root, (root / candidate).resolve()):
        errors.append("runtime.state.path must stay inside the project.")


def _check_template_file(path: Path, raw: str, where: str, errors: list[str]) -> None:
    if path.suffix.lower() not in _TEXT_SUFFIXES:
        errors.append(f"{where}: templated fixture {raw} must be text or JSON.")
        return
    try:
        path.read_text(encoding="utf-8")
    except UnicodeError:
        errors.append(f"{where}: templated fixture {raw} is not UTF-8.")
