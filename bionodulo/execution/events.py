from __future__ import annotations

from typing import Any, Awaitable, Callable

Emit = Callable[[str, dict[str, Any]], Awaitable[None]]


def make_event(event_type: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"type": event_type, "data": data}
