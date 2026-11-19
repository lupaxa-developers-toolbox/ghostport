"""Restricted templates. Lookups and a few filters only. No code execution."""

from __future__ import annotations

import json
import re
from typing import Any

from lupaxa.ghostport.errors import TemplateError

_PART = re.compile(r"\{\{\s*(.*?)\s*\}\}")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


class _Missing:
    """A path that was not in the template context."""


_MISSING = _Missing()


def render(value: Any, context: dict[str, Any]) -> Any:
    """Render templates inside JSON-like data. A whole-value lookup keeps its type."""
    if isinstance(value, str):
        return _render_string(value, context)
    if isinstance(value, list):
        return [render(item, context) for item in value]
    if isinstance(value, dict):
        return {str(key): render(item, context) for key, item in value.items()}
    return value


def _render_string(text: str, context: dict[str, Any]) -> Any:
    if "{{" not in text:
        return text
    whole = re.fullmatch(r"\s*\{\{\s*(.*?)\s*\}\}\s*", text, flags=re.DOTALL)
    if whole and whole.group(1).count("{{") == 0:
        return _eval_expr(whole.group(1), context)

    def replace(match: re.Match[str]) -> str:
        result = _eval_expr(match.group(1), context)
        if isinstance(result, str):
            return result
        if result is None:
            return ""
        return json.dumps(result, ensure_ascii=False)

    return _PART.sub(replace, text)


def _eval_expr(source: str, context: dict[str, Any]) -> Any:
    pieces = [part.strip() for part in source.split("|")]
    if not pieces or not pieces[0]:
        raise TemplateError(f"Empty template expression {source!r}.")
    current = _lookup(pieces[0], context)
    for filter_source in pieces[1:]:
        current = _apply_filter(current, filter_source, source)
    if current is _MISSING:
        raise TemplateError(f"Missing template value {pieces[0]!r}.")
    return current


def _lookup(path: str, context: dict[str, Any]) -> Any:
    parts = path.split(".")
    if not parts or any(not _IDENT.match(part) for part in parts):
        raise TemplateError(f"Unsupported template path {path!r}.")
    current: Any = context
    walked: list[str] = []
    for part in parts:
        walked.append(part)
        current = _step(current, part, ".".join(walked))
        if current is _MISSING:
            return _MISSING
    return current


def _step(current: Any, part: str, display: str) -> Any:
    if isinstance(current, dict):
        if part in current:
            return current[part]
        folded = {str(key).casefold(): key for key in current}
        original = folded.get(part.casefold())
        if original is not None:
            return current[original]
        return _MISSING
    raise TemplateError(f"Cannot read {display!r} from {type(current).__name__}.")


def _apply_filter(current: Any, source: str, expr: str) -> Any:
    name, _, argument = source.partition("(")
    name = name.strip()
    if name == "default":
        if not argument.endswith(")"):
            raise TemplateError(f"Filter default needs a value in {expr!r}.")
        if current is _MISSING:
            return _literal(argument[:-1].strip())
        return current
    if current is _MISSING:
        raise TemplateError(f"Missing template value in {expr!r}.")
    if name == "int":
        _reject_args(argument, name, expr)
        try:
            return int(current)
        except (TypeError, ValueError) as exc:
            raise TemplateError(f"Filter int failed for {current!r}.") from exc
    if name == "float":
        _reject_args(argument, name, expr)
        try:
            return float(current)
        except (TypeError, ValueError) as exc:
            raise TemplateError(f"Filter float failed for {current!r}.") from exc
    if name == "str":
        _reject_args(argument, name, expr)
        return "" if current is None else str(current)
    raise TemplateError(f"Unknown template filter {name!r}.")


def _reject_args(argument: str, name: str, expr: str) -> None:
    if argument:
        raise TemplateError(f"Filter {name} does not take arguments in {expr!r}.")


def _literal(source: str) -> Any:
    if not source:
        raise TemplateError("Filter default needs a value.")
    try:
        return json.loads(source)
    except json.JSONDecodeError as exc:
        raise TemplateError(f"Default {source!r} is not a JSON literal.") from exc
