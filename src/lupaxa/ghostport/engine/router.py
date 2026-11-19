"""Match a request to one route. Higher priority wins, then declaration order."""

from __future__ import annotations

import re
from dataclasses import dataclass

from lupaxa.ghostport.config.models import MatchDef, RouteDef
from lupaxa.ghostport.config.paths import compile_path


@dataclass(frozen=True)
class CompiledRoute:
    route: RouteDef
    pattern: re.Pattern[str]
    names: tuple[str, ...]


def compile_routes(routes: tuple[RouteDef, ...]) -> tuple[CompiledRoute, ...]:
    compiled = [CompiledRoute(route, *compile_path(route.path)) for route in routes]
    return tuple(sorted(compiled, key=lambda item: (-item.route.priority, item.route.index)))


def match_route(
    routes: tuple[CompiledRoute, ...],
    method: str,
    path: str,
    query: dict[str, list[str]],
    headers: dict[str, str],
) -> tuple[RouteDef, dict[str, str]] | None:
    for item in routes:
        if item.route.method != method.upper():
            continue
        found = item.pattern.match(path)
        if found is None or not _conditions(item.route.match, query, headers):
            continue
        return item.route, dict(zip(item.names, found.groups(), strict=True))
    return None


def _conditions(match: MatchDef, query: dict[str, list[str]], headers: dict[str, str]) -> bool:
    folded = {key.casefold(): value for key, value in headers.items()}
    query_folded = {key.casefold(): value for key, value in query.items()}
    for name, expected in match.query:
        values = query_folded.get(name.casefold())
        if values is None or expected not in values:
            return False
    for name in match.query_present:
        if name.casefold() not in query_folded:
            return False
    for name, expected in match.headers:
        if folded.get(name.casefold()) != expected:
            return False
    return all(name.casefold() in folded for name in match.headers_present)
