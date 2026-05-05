from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class Event:
    type: str
    data: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"type": self.type, "data": self.data}


class EventHub:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[Event]] = set()

    def subscribe(self) -> asyncio.Queue[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        self._subscribers.discard(queue)

    async def emit(self, event_type: str, data: dict[str, Any]) -> None:
        event = Event(event_type, data)
        dead: list[asyncio.Queue[Event]] = []
        for subscriber in self._subscribers:
            try:
                subscriber.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(subscriber)
        for subscriber in dead:
            self.unsubscribe(subscriber)


event_hub = EventHub()
