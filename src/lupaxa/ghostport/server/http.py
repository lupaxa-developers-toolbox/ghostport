"""HTTP adapter for one API engine. Generated responses are never executed."""

from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from lupaxa.ghostport.engine.api import ApiEngine, Incoming


class ApiServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, host: str, port: int, engine: ApiEngine, verbose: bool = False) -> None:
        super().__init__((host, port), ApiHandler)
        self.engine = engine
        self.verbose = verbose


class ApiHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: ApiServer

    def handle(self) -> None:
        self.connection.settimeout(self.server.engine.project.server.request_timeout)
        super().handle()

    def do_GET(self) -> None:
        self._serve()

    def do_POST(self) -> None:
        self._serve()

    def do_PUT(self) -> None:
        self._serve()

    def do_PATCH(self) -> None:
        self._serve()

    def do_DELETE(self) -> None:
        self._serve()

    def do_HEAD(self) -> None:
        self._serve()

    def do_OPTIONS(self) -> None:
        self._serve()

    def _serve(self) -> None:
        limit = self.server.engine.project.server.max_request_body
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = limit + 1
        if length > limit:
            body = b'{"error":"Payload too large"}'
            self._write(
                413,
                {
                    "Content-Type": "application/json; charset=utf-8",
                    "Content-Length": str(len(body)),
                },
                body,
            )
            return
        payload = self.rfile.read(length) if length else b""
        parts = urlsplit(self.path)
        incoming = Incoming(
            method=self.command,
            path=parts.path,
            query=parse_qs(parts.query, keep_blank_values=True),
            headers={key: value for key, value in self.headers.items()},
            body=payload,
        )
        outgoing = self.server.engine.handle(incoming)
        self._write(outgoing.status, outgoing.headers, outgoing.body)

    def _write(self, status: int, headers: dict[str, str], body: bytes) -> None:
        self.send_response(status)
        for key, value in headers.items():
            if key.lower() == "content-length":
                continue
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        if self.server.verbose:
            path = urlsplit(self.path).path
            sys.stderr.write(f"{self.command} {path}\n")
