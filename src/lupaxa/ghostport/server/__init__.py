"""Start the simulated API and the separate management listener."""

from __future__ import annotations

import threading

from lupaxa.ghostport.config.models import ResolvedProject
from lupaxa.ghostport.engine.api import ApiEngine
from lupaxa.ghostport.server.http import ApiServer
from lupaxa.ghostport.server.management import ManagementServer


def start_servers(
    project: ResolvedProject,
    *,
    host: str | None = None,
    port: int | None = None,
    scenario: str | None = None,
    management_port: int | None = None,
    verbose: bool = False,
) -> tuple[ApiServer, ManagementServer | None]:
    """Bind listeners and serve them on daemon threads. Returns the server objects."""
    engine = ApiEngine(project)
    if scenario:
        engine.set_scenario(scenario)
    api = ApiServer(
        host or project.server.host,
        project.server.port if port is None else port,
        engine,
        verbose,
    )
    management: ManagementServer | None = None
    if project.management.enabled:
        management = ManagementServer(
            project.management.host,
            project.management.port if management_port is None else management_port,
            engine,
        )
    threading.Thread(target=api.serve_forever, name="ghostport-api", daemon=True).start()
    if management is not None:
        threading.Thread(
            target=management.serve_forever,
            name="ghostport-management",
            daemon=True,
        ).start()
    return api, management
