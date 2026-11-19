"""Locate a project and read YAML or JSON documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from lupaxa.ghostport.errors import ConfigError

_ROOT_NAMES = ("ghostport.yml", "ghostport.yaml", "ghostport.json")
_SUFFIXES = {".yml", ".yaml", ".json"}


def find_project(source: Path) -> tuple[Path, Path]:
    """Return ``(root file, project directory)`` for a file or a directory."""
    source = source.expanduser()
    if source.is_dir():
        found = [path for name in _ROOT_NAMES if (path := source / name).is_file()]
        if not found:
            raise ConfigError([f"No ghostport.yml in {source}."])
        if len(found) > 1:
            names = ", ".join(path.name for path in found)
            raise ConfigError([f"Multiple root files in {source}: {names}."])
        return found[0].resolve(), source.resolve()
    if source.is_file():
        if source.suffix.lower() not in _SUFFIXES:
            raise ConfigError([f"{source}: configuration files must be .yml, .yaml, or .json."])
        return source.resolve(), source.resolve().parent
    raise ConfigError([f"Project path does not exist: {source}."])


def read_document(path: Path) -> tuple[Any, str | None]:
    """Return ``(document, error)``. An empty file is an empty mapping."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        reason = exc.strerror or "could not be read"
        return None, f"{path}: {reason}."
    except UnicodeError:
        return None, f"{path}: file is not UTF-8."
    if path.suffix.lower() not in _SUFFIXES:
        return None, f"{path}: configuration files must be .yml, .yaml, or .json."
    try:
        if path.suffix.lower() == ".json":
            data = json.loads(text) if text.strip() else {}
        else:
            data = yaml.safe_load(text)
    except (yaml.YAMLError, json.JSONDecodeError, UnicodeError) as exc:
        return None, f"{path}: {exc}."
    if data is None:
        return {}, None
    return data, None


def inside(root: Path, path: Path) -> bool:
    """True when ``path`` stays inside ``root`` after resolving symlinks."""
    return path.resolve().is_relative_to(root.resolve())


def resolve_include(root: Path, raw: str, where: str, errors: list[str]) -> Path | None:
    """Resolve one include path. Absolute paths may leave the project. Globs may not."""
    if not isinstance(raw, str) or not raw.strip():
        errors.append(f"{where}: include path must be a file name.")
        return None
    if any(char in raw for char in "*?[]"):
        errors.append(f"{where}: glob {raw!r} is not supported. List each file.")
        return None
    candidate = Path(raw)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (root / candidate).resolve()
        if not inside(root, resolved):
            errors.append(f"{where}: {raw} escapes the project root.")
            return None
    if not resolved.is_file():
        errors.append(f"{where}: missing file {raw}.")
        return None
    return resolved


def resolve_fixture(root: Path, raw: str, where: str, errors: list[str]) -> Path | None:
    """Resolve a fixture. Relative paths must stay inside the project."""
    if not isinstance(raw, str) or not raw.strip():
        errors.append(f"{where}: file path must be a string.")
        return None
    candidate = Path(raw)
    if candidate.is_absolute():
        errors.append(f"{where}: fixture {raw} must be a path inside the project.")
        return None
    resolved = (root / candidate).resolve()
    if not inside(root, resolved):
        errors.append(f"{where}: {raw} escapes the project root.")
        return None
    if not resolved.is_file():
        errors.append(f"{where}: missing fixture {raw}.")
        return None
    return resolved
