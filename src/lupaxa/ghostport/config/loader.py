"""Load a single-file or directory project into one resolved definition."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lupaxa.ghostport.config.includes import find_project, read_document, resolve_include
from lupaxa.ghostport.config.models import CollectionDef, ResolvedProject, StateDef, ValueDef
from lupaxa.ghostport.config.resolver import assemble
from lupaxa.ghostport.config.validator import (
    parse_api,
    parse_management,
    parse_routes,
    parse_runtime,
    parse_scenarios,
    parse_server,
    parse_state,
    unknown,
)
from lupaxa.ghostport.errors import ConfigError


def load_project(source: Path | str) -> ResolvedProject:
    """Read, combine, and validate a project. Raise before any listener opens."""
    root_file, project_root = find_project(Path(source))
    errors: list[str] = []
    document, error = read_document(root_file)
    if error is not None:
        raise ConfigError([error])
    if not isinstance(document, dict):
        raise ConfigError([f"{root_file.name}: the root document must be a mapping."])
    project = _combine(document, root_file, project_root, errors)
    if project is None:
        raise ConfigError(errors or ["Invalid configuration."])
    return project


def _combine(
    document: dict[str, Any],
    root_file: Path,
    project_root: Path,
    errors: list[str],
) -> ResolvedProject | None:
    unknown(
        document,
        {
            "version",
            "api",
            "server",
            "routes",
            "scenarios",
            "state",
            "include",
            "runtime",
            "management",
        },
        root_file.name,
        errors,
    )
    version = document.get("version")
    if version != 1:
        errors.append(f"{root_file.name}: version must be 1.")
        version = 1
    api = parse_api(document.get("api"), errors)
    server = parse_server(document.get("server"), errors)
    runtime = parse_runtime(document.get("runtime"), errors)
    management = parse_management(document.get("management"), errors)
    routes = parse_routes(document.get("routes"), f"{root_file.name}:routes", errors, 0)
    scenarios = parse_scenarios(document.get("scenarios"), f"{root_file.name}:scenarios", errors)
    collections, values = parse_state(document.get("state"), f"{root_file.name}:state", errors)
    _includes(
        document.get("include"),
        project_root,
        root_file.name,
        routes,
        scenarios,
        collections,
        values,
        errors,
    )
    _duplicate_state(collections, values, errors)
    return assemble(
        version=int(version) if version == 1 else 1,
        api=api,
        server=server,
        routes=routes,
        scenarios=scenarios,
        state=StateDef(tuple(collections), tuple(values)),
        runtime=runtime,
        management=management,
        root=project_root,
        errors=errors,
    )


def _includes(
    raw: Any,
    root: Path,
    where: str,
    routes: list[Any],
    scenarios: list[Any],
    collections: list[CollectionDef],
    values: list[ValueDef],
    errors: list[str],
) -> None:
    if raw is None:
        return
    if not isinstance(raw, dict):
        errors.append(f"{where}: include must be a mapping.")
        return
    unknown(raw, {"routes", "scenarios", "state"}, f"{where}:include", errors)
    for kind in ("routes", "scenarios", "state"):
        items = raw.get(kind, [])
        if items is None:
            continue
        if not isinstance(items, list):
            errors.append(f"{where}: include.{kind} must be a list of files.")
            continue
        for index, item in enumerate(items):
            place = f"{where}:include.{kind}[{index}]"
            path = resolve_include(root, item, place, errors) if isinstance(item, str) else None
            if not isinstance(item, str):
                errors.append(f"{place}: include path must be a string.")
                continue
            if path is None:
                continue
            document, error = read_document(path)
            label = path.name
            if error is not None:
                errors.append(error)
                continue
            if not isinstance(document, dict):
                errors.append(f"{label}: document must be a mapping.")
                continue
            if "include" in document:
                errors.append(f"{label}: included files cannot include other files.")
            if kind == "routes":
                unknown(document, {"routes"}, label, errors)
                routes.extend(
                    parse_routes(document.get("routes"), f"{label}:routes", errors, len(routes))
                )
            elif kind == "scenarios":
                unknown(document, {"scenarios"}, label, errors)
                scenarios.extend(
                    parse_scenarios(document.get("scenarios"), f"{label}:scenarios", errors)
                )
            else:
                unknown(document, {"state"}, label, errors)
                more_collections, more_values = parse_state(
                    document.get("state"),
                    f"{label}:state",
                    errors,
                )
                collections.extend(more_collections)
                values.extend(more_values)


def _duplicate_state(
    collections: list[CollectionDef], values: list[ValueDef], errors: list[str]
) -> None:
    seen: set[str] = set()
    for name in [item.name for item in collections] + [item.name for item in values]:
        if name in seen:
            errors.append(f"Duplicate state name {name!r}.")
        seen.add(name)
