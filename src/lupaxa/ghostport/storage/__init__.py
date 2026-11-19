"""State backends. Each engine owns one store."""

from __future__ import annotations

from pathlib import Path

from lupaxa.ghostport.config.includes import inside
from lupaxa.ghostport.config.models import ResolvedProject
from lupaxa.ghostport.errors import ConfigError
from lupaxa.ghostport.storage.memory import MemoryStore
from lupaxa.ghostport.storage.sqlite import SqliteStore

Store = MemoryStore | SqliteStore


def open_store(project: ResolvedProject) -> Store:
    """Open the store selected by ``runtime.state.persistence``."""
    if project.runtime.state.persistence == "memory":
        return MemoryStore(project.state)
    relative = project.runtime.state.path or ".ghostport/state.sqlite"
    candidate = Path(relative)
    resolved = (project.project_root / candidate).resolve()
    if candidate.is_absolute() or not inside(project.project_root, resolved):
        raise ConfigError(["runtime.state.path must stay inside the project."])
    return SqliteStore(resolved, project.state)
