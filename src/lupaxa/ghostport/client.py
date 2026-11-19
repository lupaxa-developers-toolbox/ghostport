"""Talk to a running management interface. Payloads are not shell commands."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from lupaxa.ghostport.errors import GhostPortError, UsageError


def request_json(url: str, method: str = "GET", payload: Any = None, timeout: float = 5) -> Any:
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        message = detail
        try:
            parsed = json.loads(detail)
            if isinstance(parsed, dict) and "error" in parsed:
                message = str(parsed["error"])
        except json.JSONDecodeError:
            message = detail or exc.reason
        raise UsageError(message) from exc
    except urllib.error.URLError as exc:
        raise GhostPortError(
            f"Management interface is not reachable at {url}: {exc.reason}"
        ) from exc
    if not raw:
        return None
    return json.loads(raw.decode())
