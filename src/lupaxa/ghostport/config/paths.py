"""URL path patterns such as ``/users/{id}``."""

from __future__ import annotations

import re

_TOKEN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def compile_path(pattern: str) -> tuple[re.Pattern[str], tuple[str, ...]]:
    """Compile a path pattern. Raises ``ValueError`` when the pattern is unusable."""
    if not pattern.startswith("/"):
        raise ValueError("path must start with /.")
    names: list[str] = []
    pieces: list[str] = []
    index = 0
    while index < len(pattern):
        if pattern[index] == "{":
            end = pattern.find("}", index)
            if end < 0:
                raise ValueError("path has an unclosed parameter.")
            name = pattern[index + 1 : end]
            if not _TOKEN.match(name):
                raise ValueError(f"path parameter {name!r} is not a name.")
            if name in names:
                raise ValueError(f"path parameter {name!r} is repeated.")
            names.append(name)
            pieces.append(r"([^/]+)")
            index = end + 1
            continue
        if pattern[index] == "}":
            raise ValueError("path has an extra }.")
        pieces.append(re.escape(pattern[index]))
        index += 1
    return re.compile("^" + "".join(pieces) + "$"), tuple(names)


def path_shape(pattern: str) -> str:
    """Hide parameter names so ``/users/{id}`` and ``/users/{name}`` compare equal."""
    return re.sub(r"\{[^{}]+\}", "{}", pattern)
