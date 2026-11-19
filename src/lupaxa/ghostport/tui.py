"""Textual inspector for a running Ghost Port management interface."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Static

from lupaxa.ghostport.client import request_json


class GhostPortApp(App[None]):
    """Show the active scenario and recent requests. Press r to refresh."""

    TITLE = "Ghostport"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_view", "Refresh"),
    ]

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url.rstrip("/")

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Connecting", id="status")
        yield DataTable(id="history")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Time", "Method", "Path", "Status", "Route")
        self.set_interval(1, self.action_refresh_view)
        self.action_refresh_view()

    def action_refresh_view(self) -> None:
        status = self.query_one("#status", Static)
        table = self.query_one(DataTable)
        try:
            current = request_json(f"{self.base_url}/status")
            history = request_json(f"{self.base_url}/history")
        except Exception as exc:
            status.update(f"Management unavailable: {exc}")
            return
        status.update(
            f"{current['api']}  scenario {current['scenario']}  routes {current['routes']}"
        )
        table.clear()
        for entry in history.get("entries", []):
            table.add_row(
                entry.get("timestamp", ""),
                entry.get("method", ""),
                entry.get("path", ""),
                str(entry.get("status", "")),
                entry.get("route") or "",
            )


def run_tui(base_url: str) -> None:
    GhostPortApp(base_url).run()
