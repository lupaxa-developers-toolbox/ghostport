"""Errors for configuration, templates, and runtime failures."""

from __future__ import annotations


class GhostPortError(Exception):
    """Base error. ``exit_code`` is what the CLI returns."""

    exit_code = 1

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.messages = [message]


class ConfigError(GhostPortError):
    """One or more configuration problems. The server must not start."""

    exit_code = 2

    def __init__(self, messages: list[str]) -> None:
        text = "\n".join(messages) if messages else "Invalid configuration."
        super().__init__(text)
        self.messages = list(messages) or [text]


class UsageError(GhostPortError):
    """The command line or a management request was not valid."""

    exit_code = 2


class TemplateError(GhostPortError):
    """A response template could not be rendered."""

    exit_code = 1
