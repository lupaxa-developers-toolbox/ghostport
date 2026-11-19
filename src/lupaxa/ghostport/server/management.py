"""Localhost control plane. It does not share the simulated API routes."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from lupaxa.ghostport.engine.api import ApiEngine
from lupaxa.ghostport.errors import UsageError


class ManagementServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, host: str, port: int, engine: ApiEngine) -> None:
        super().__init__((host, port), ManagementHandler)
        self.engine = engine


class ManagementHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: ManagementServer

    def do_GET(self) -> None:
        self._dispatch()

    def do_PUT(self) -> None:
        self._dispatch()

    def do_POST(self) -> None:
        self._dispatch()

    def do_DELETE(self) -> None:
        self._dispatch()

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _dispatch(self) -> None:
        path = urlsplit(self.path).path.rstrip("/") or "/"
        engine = self.server.engine
        try:
            if self.command == "GET" and path == "/status":
                self._json(200, engine.status())
                return
            if self.command == "GET" and path == "/scenario":
                self._json(200, _scenario(engine))
                return
            if self.command in {"PUT", "POST"} and path == "/scenario":
                engine.set_scenario(str(_object(self).get("id", "")))
                self._json(200, _scenario(engine))
                return
            if self.command == "POST" and path == "/scenario/reset":
                engine.reset_scenario()
                self._json(200, _scenario(engine))
                return
            if self.command == "GET" and path == "/state":
                self._json(200, engine.store.snapshot())
                return
            if self.command == "POST" and path == "/state/reset":
                engine.reset_state()
                self._json(200, {"reset": True})
                return
            if self.command == "POST" and path == "/sequence/reset":
                raw = _object(self)
                route = raw.get("route")
                engine.reset_sequence(None if route in (None, "") else str(route))
                self._json(200, {"reset": True})
                return
            if self.command == "GET" and path == "/history":
                entries = [item.to_dict() for item in engine.history.list_entries()]
                self._json(200, {"entries": entries})
                return
            if self.command == "GET" and path.startswith("/history/"):
                entry = engine.history.get(path.removeprefix("/history/"))
                if entry is None:
                    self._json(404, {"error": "Not Found"})
                    return
                self._json(200, entry.to_dict())
                return
            if self.command == "DELETE" and path == "/history":
                engine.history.clear()
                self._json(200, {"cleared": True})
                return
            if self.command == "GET" and path == "/config":
                self._json(200, engine.project.to_dict())
                return
        except UsageError as exc:
            self._json(400, {"error": str(exc)})
            return
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        self._json(404, {"error": "Not Found"})

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _scenario(engine: ApiEngine) -> dict[str, str]:
    description = ""
    for scenario in engine.project.scenarios:
        if scenario.id == engine.scenario_id:
            description = scenario.description
    return {"id": engine.scenario_id, "description": description}


def _object(handler: ManagementHandler) -> dict[str, object]:
    length = int(handler.headers.get("Content-Length") or 0)
    raw = handler.rfile.read(length) if length else b"{}"
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("JSON object required.")
    return parsed
