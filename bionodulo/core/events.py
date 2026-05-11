"""EventHub for pub/sub pattern used by WebSocket broadcasting.

Provides asyncio-based event distribution with typed event envelopes.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Event:
    """A typed event envelope for the EventHub.

    Attributes:
        type: Event type string (e.g. "execution.started", "node.completed").
        data: Payload dictionary with event-specific data.
        source: Optional source identifier (run_id, node_id, etc.).
        event_id: Unique event identifier for deduplication/tracing.
    """

    type: str
    data: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "type": self.type,
            "source": self.source,
            "data": self.data,
        }


class EventHub:
    """Async pub/sub event hub for broadcasting execution updates.

    Uses asyncio.Queue for distribution to WebSocket consumers.
    Supports filtered subscriptions by event type prefix.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, asyncio.Queue[Event]] = {}
        self._filters: dict[str, str] = {}
        self._callbacks: list[tuple[str, Callable[[Event], Any]]] = []
        self._lock = asyncio.Lock()

    async def subscribe(
        self,
        filter_prefix: str = "",
    ) -> str:
        """Subscribe to events and return a subscription ID.

        Args:
            filter_prefix: Only emit events whose type starts with this prefix.
                          Empty string means no filtering (all events).

        Returns:
            Subscription ID string for unsubscribing.
        """
        sub_id = str(uuid.uuid4())
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=1000)
        async with self._lock:
            self._subscribers[sub_id] = queue
            self._filters[sub_id] = filter_prefix
        return sub_id

    async def unsubscribe(self, sub_id: str) -> None:
        """Remove a subscription by ID."""
        async with self._lock:
            self._subscribers.pop(sub_id, None)
            self._filters.pop(sub_id, None)

    async def emit(self, event: Event) -> None:
        """Emit an event to all matching subscribers.

        Args:
            event: The Event to distribute.
        """
        async with self._lock:
            subscribers_snapshot = list(self._subscribers.items())
            filters_snapshot = dict(self._filters)
            callbacks = list(self._callbacks)

        for sub_id, queue in subscribers_snapshot:
            filter_prefix = filters_snapshot.get(sub_id, "")
            if filter_prefix and not event.type.startswith(filter_prefix):
                continue
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

        for filter_prefix, callback in callbacks:
            if filter_prefix and not event.type.startswith(filter_prefix):
                continue
            try:
                result = callback(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass

    async def emit_typed(
        self,
        event_type: str,
        data: dict[str, Any],
        source: str = "",
    ) -> None:
        """Convenience method to create and emit an event in one call."""
        event = Event(type=event_type, data=data, source=source)
        await self.emit(event)

    async def get_queue(self, sub_id: str) -> asyncio.Queue[Event] | None:
        """Get the queue for a subscription ID."""
        return self._subscribers.get(sub_id)

    def add_callback(
        self,
        callback: Callable[[Event], Any],
        filter_prefix: str = "",
    ) -> None:
        """Add a synchronous or async callback for events."""
        self._callbacks.append((filter_prefix, callback))

    def remove_callback(
        self,
        callback: Callable[[Event], Any],
    ) -> None:
        """Remove a callback."""
        self._callbacks = [
            pair for pair in self._callbacks if pair[1] is not callback
        ]

    @property
    def subscriber_count(self) -> int:
        """Return the number of active subscribers."""
        return len(self._subscribers)
