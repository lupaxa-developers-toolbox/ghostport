"""The ghostport command."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import yaml

from lupaxa.ghostport.client import request_json
from lupaxa.ghostport.config.includes import find_project
from lupaxa.ghostport.config.loader import load_project
from lupaxa.ghostport.errors import ConfigError, GhostPortError, UsageError
from lupaxa.ghostport.server import start_servers
from lupaxa.ghostport.version import __version__

_SINGLE = """version: 1

api:
  name: example-api
  description: A simple example API

server:
  host: 127.0.0.1
  port: 8080

routes:
  - id: list-users
    method: GET
    path: /users
    response:
      status: 200
      json:
        users:
          - id: 1
            name: Alice
          - id: 2
            name: Bob

  - id: health
    method: GET
    path: /health
    response:
      status: 200
      json:
        status: healthy
"""

_ROOT = """version: 1

api:
  name: {name}
  description: Simulated API

server:
  host: 127.0.0.1
  port: 8080

include:
  routes:
    - routes/example.yml
  scenarios:
    - scenarios/normal.yml

runtime:
  scenario: normal
"""

_ROUTE = """routes:
  - id: list-users
    method: GET
    path: /users
    response:
      status: 200
      json:
        users:
          - id: 1
            name: Alice
"""

_NORMAL = """scenarios:
  - id: normal
    description: Normal API behaviour
"""


def main(argv: list[str] | None = None) -> int:
    """Run one Ghost Port command."""
    parser = _parser()
    try:
        args = parser.parse_args(argv)
        if not getattr(args, "command", None):
            parser.print_help()
            return 0
        return int(args.handler(args))
    except ConfigError as exc:
        for message in exc.messages:
            print(message, file=sys.stderr)
        return exc.exit_code
    except GhostPortError as exc:
        print(exc, file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        return 130
    except OSError as exc:
        print(exc, file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ghostport",
        description="Simulate HTTP APIs from declarative YAML projects.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command")

    serve = commands.add_parser("serve", help="Serve a project")
    serve.add_argument("project")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    serve.add_argument("--scenario")
    serve.add_argument("--management-port", type=int)
    serve.add_argument("--verbose", action="store_true")
    serve.set_defaults(handler=cmd_serve)

    validate = commands.add_parser("validate", help="Validate a project")
    validate.add_argument("project")
    validate.set_defaults(handler=cmd_validate)

    init = commands.add_parser("init", help="Create a project")
    init.add_argument("path")
    init.add_argument("--single-file", action="store_true")
    init.add_argument("--force", action="store_true")
    init.set_defaults(handler=cmd_init)

    config = commands.add_parser("config", help="Show configuration")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    show = config_commands.add_parser("show", help="Show the project configuration")
    show.add_argument("project")
    show.add_argument("--resolved", action="store_true")
    show.add_argument("--format", choices=("yaml", "json"), default="yaml")
    show.set_defaults(handler=cmd_config_show, command="config")

    scenario = commands.add_parser("scenario", help="Inspect or change the active scenario")
    scenario_commands = scenario.add_subparsers(dest="scenario_command", required=True)
    listing = scenario_commands.add_parser("list", help="List scenarios")
    listing.add_argument("project", nargs="?")
    listing.add_argument("--url", default="http://127.0.0.1:8081")
    listing.set_defaults(handler=cmd_scenario_list, command="scenario")
    shown = scenario_commands.add_parser("show", help="Show one scenario")
    shown.add_argument("scenario_id")
    shown.add_argument("project", nargs="?")
    shown.add_argument("--url", default="http://127.0.0.1:8081")
    shown.set_defaults(handler=cmd_scenario_show, command="scenario")
    chosen = scenario_commands.add_parser("set", help="Activate a scenario")
    chosen.add_argument("scenario_id")
    chosen.add_argument("--url", default="http://127.0.0.1:8081")
    chosen.set_defaults(handler=cmd_scenario_set, command="scenario")
    reset = scenario_commands.add_parser("reset", help="Restore the configured scenario")
    reset.add_argument("--url", default="http://127.0.0.1:8081")
    reset.set_defaults(handler=cmd_scenario_reset, command="scenario")

    state = commands.add_parser("state", help="Inspect or reset simulated state")
    state_commands = state.add_subparsers(dest="state_command", required=True)
    state_show = state_commands.add_parser("show", help="Show current state")
    state_show.add_argument("--url", default="http://127.0.0.1:8081")
    state_show.set_defaults(handler=cmd_state_show, command="state")
    state_reset = state_commands.add_parser("reset", help="Restore the initial state")
    state_reset.add_argument("--url", default="http://127.0.0.1:8081")
    state_reset.set_defaults(handler=cmd_state_reset, command="state")

    sequence = commands.add_parser("sequence", help="Reset response sequences")
    sequence_commands = sequence.add_subparsers(dest="sequence_command", required=True)
    sequence_reset = sequence_commands.add_parser(
        "reset",
        help="Reset one sequence or all sequences",
    )
    sequence_reset.add_argument("route", nargs="?")
    sequence_reset.add_argument("--url", default="http://127.0.0.1:8081")
    sequence_reset.set_defaults(handler=cmd_sequence_reset, command="sequence")

    history = commands.add_parser("history", help="Inspect recorded requests")
    history_commands = history.add_subparsers(dest="history_command", required=True)
    history_list = history_commands.add_parser("list", help="List recorded requests")
    history_list.add_argument("--url", default="http://127.0.0.1:8081")
    history_list.set_defaults(handler=cmd_history_list, command="history")
    history_show = history_commands.add_parser("show", help="Show one recorded request")
    history_show.add_argument("request_id")
    history_show.add_argument("--url", default="http://127.0.0.1:8081")
    history_show.set_defaults(handler=cmd_history_show, command="history")
    history_clear = history_commands.add_parser("clear", help="Delete recorded requests")
    history_clear.add_argument("--url", default="http://127.0.0.1:8081")
    history_clear.set_defaults(handler=cmd_history_clear, command="history")

    tui = commands.add_parser("tui", help="Open the management inspector")
    tui.add_argument("--url", default="http://127.0.0.1:8081")
    tui.add_argument("--serve", help="Start this project, then open the inspector")
    tui.set_defaults(handler=cmd_tui)
    return parser


def cmd_serve(args: argparse.Namespace) -> int:
    project = load_project(args.project)
    api, management = start_servers(
        project,
        host=args.host,
        port=args.port,
        scenario=args.scenario,
        management_port=args.management_port,
        verbose=args.verbose,
    )
    host, port = api.server_address[:2]
    print(f"Ghost Port listening on http://{host!s}:{port!s}", file=sys.stderr)
    if management is not None:
        mhost, mport = management.server_address[:2]
        print(f"Management listening on http://{mhost!s}:{mport!s}", file=sys.stderr)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        _stop(api, management)
        return 130


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        project = load_project(args.project)
    except ConfigError as exc:
        print("Ghost Port Configuration Validation\n", file=sys.stderr)
        for message in exc.messages:
            print(message, file=sys.stderr)
        print("\nValidation failed.", file=sys.stderr)
        return 2
    print("Ghost Port Configuration Validation\n")
    print(f"Project: {project.api.name}")
    print(f"Schema:  {project.version}\n")
    print(f"Routes:       {len(project.routes)}")
    print(f"Scenarios:     {len(project.scenarios)}")
    state_sets = len(project.state.collections) + len(project.state.values)
    print(f"State sets:    {state_sets}")
    print(f"Fixtures:      {len(project.fixtures)}\n")
    print("Validation successful.")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    destination = Path(args.path)
    name = destination.name or "example-api"
    if args.single_file:
        _write(destination / "ghostport.yml", _SINGLE, args.force)
        return 0
    _write(destination / "ghostport.yml", _ROOT.format(name=name), args.force)
    _write(destination / "routes" / "example.yml", _ROUTE, args.force)
    _write(destination / "scenarios" / "normal.yml", _NORMAL, args.force)
    (destination / "fixtures").mkdir(parents=True, exist_ok=True)
    return 0


def cmd_config_show(args: argparse.Namespace) -> int:
    if not args.resolved:
        root, _directory = find_project(Path(args.project))
        sys.stdout.write(root.read_text(encoding="utf-8"))
        if not root.read_text(encoding="utf-8").endswith("\n"):
            sys.stdout.write("\n")
        return 0
    project = load_project(args.project)
    if args.format == "json":
        print(json.dumps(project.to_dict(), indent=2, ensure_ascii=False))
        return 0
    print(yaml.safe_dump(project.to_dict(), sort_keys=False), end="")
    return 0


def cmd_scenario_list(args: argparse.Namespace) -> int:
    if args.project:
        project = load_project(args.project)
        if not project.scenarios:
            print("normal")
            return 0
        for scenario in project.scenarios:
            print(f"{scenario.id}\t{scenario.description}")
        return 0
    status = request_json(f"{args.url}/status")
    active = status["scenario"]
    names = status["scenarios"] or ["normal"]
    for name in names:
        marker = "*" if name == active else " "
        print(f"{marker} {name}")
    return 0


def cmd_scenario_show(args: argparse.Namespace) -> int:
    if args.project:
        project = load_project(args.project)
        scenarios = [item.to_dict() for item in project.scenarios]
    else:
        scenarios = request_json(f"{args.url}/config")["scenarios"]
    for scenario in scenarios:
        if scenario["id"] == args.scenario_id:
            print(yaml.safe_dump(scenario, sort_keys=False), end="")
            return 0
    raise UsageError(f"Unknown scenario {args.scenario_id!r}.")


def cmd_scenario_set(args: argparse.Namespace) -> int:
    body = request_json(f"{args.url}/scenario", "PUT", {"id": args.scenario_id})
    print(body["id"])
    return 0


def cmd_scenario_reset(args: argparse.Namespace) -> int:
    body = request_json(f"{args.url}/scenario/reset", "POST", {})
    print(body["id"])
    return 0


def cmd_state_show(args: argparse.Namespace) -> int:
    print(json.dumps(request_json(f"{args.url}/state"), indent=2, ensure_ascii=False))
    return 0


def cmd_state_reset(args: argparse.Namespace) -> int:
    request_json(f"{args.url}/state/reset", "POST", {})
    print("reset")
    return 0


def cmd_sequence_reset(args: argparse.Namespace) -> int:
    payload: dict[str, Any] = {} if not args.route else {"route": args.route}
    request_json(f"{args.url}/sequence/reset", "POST", payload)
    print("reset")
    return 0


def cmd_history_list(args: argparse.Namespace) -> int:
    entries = request_json(f"{args.url}/history")["entries"]
    for entry in entries:
        route = entry.get("route") or "-"
        print(
            f"{entry['request_id']}  {entry['method']} {entry['path']}  {entry['status']}  {route}"
        )
    return 0


def cmd_history_show(args: argparse.Namespace) -> int:
    entry = request_json(f"{args.url}/history/{args.request_id}")
    print(json.dumps(entry, indent=2, ensure_ascii=False))
    return 0


def cmd_history_clear(args: argparse.Namespace) -> int:
    request_json(f"{args.url}/history", "DELETE")
    print("cleared")
    return 0


def cmd_tui(args: argparse.Namespace) -> int:
    servers: tuple[Any, Any] | None = None
    url = args.url
    if args.serve:
        project = load_project(args.serve)
        api, management = start_servers(project, port=0, management_port=0)
        servers = (api, management)
        if management is None:
            _stop(api, None)
            raise UsageError("The management interface is disabled.")
        bound = management.server_address
        url = f"http://{bound[0]!s}:{bound[1]!s}"
    try:
        from lupaxa.ghostport.tui import run_tui
    except ImportError as exc:
        raise UsageError("The Textual package is required for ghostport tui.") from exc
    try:
        run_tui(url)
    finally:
        if servers is not None:
            _stop(servers[0], servers[1])
    return 0


def _write(path: Path, text: str, force: bool) -> None:
    if path.exists() and not force:
        raise UsageError(f"{path} already exists. Use --force to overwrite it.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _stop(api: Any, management: Any) -> None:
    api.shutdown()
    if management is not None:
        management.shutdown()
