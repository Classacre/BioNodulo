"""Redis Pub/Sub broadcaster for horizontal scaling with in-memory fallback.

When a Redis URL is provided and the server is reachable, messages are
published to Redis channels so that multiple BioNodulo server instances
can share collaboration rooms.  If Redis is unavailable or no URL is
given, the broadcaster falls back to an in-memory dictionary that works
for single-instance deployments.

Channel naming: ``bionodulo:room:{room_id}``

Usage::

    broadcaster = RedisBroadcaster("redis://localhost:6379/0")
    await broadcaster.subscribe("workflow-123", on_message)
    await broadcaster.publish("workflow-123", b"binary data")
    await broadcaster.unsubscribe("workflow-123")
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Default Redis URL from environment
DEFAULT_REDIS_URL_ENV = "BIONODULO_REDIS_URL"

# Channel prefix
_CHANNEL_PREFIX = "bionodulo:room:"


class RedisBroadcaster:
    """Broadcasts binary messages to collaboration rooms.

    Attempts to use Redis Pub/Sub; falls back to in-memory delivery
    if Redis is unavailable.
    """

    def __init__(self, redis_url: str | None = None) -> None:
        """Initialise the broadcaster.

        Args:
            redis_url: Redis connection URL.  If ``None``, the value of
                the ``BIONODULO_REDIS_URL`` environment variable is used.
                If that is also unset, the in-memory fallback is used.
        """
        import os

        self._redis_url = redis_url or os.environ.get(DEFAULT_REDIS_URL_ENV, "")
        self._redis_client: Any | None = None
        self._pubsub: Any | None = None
        self._redis_available: bool = False

        # In-memory fallback: room_id -> list[callback]
        self._memory_subs: dict[str, list[Callable[[bytes], Any]]] = {}
        self._memory_lock = asyncio.Lock()

        # Background listener task for Redis
        self._listener_task: asyncio.Task[Any] | None = None

        # Message callback router for Redis -> local
        self._local_callbacks: dict[str, list[Callable[[bytes], Any]]] = {}

    # ------------------------------------------------------------------
    # Redis connection
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Attempt to connect to Redis.

        Returns:
            ``True`` if the connection succeeded.
        """
        if not self._redis_url:
            logger.info("No Redis URL configured — using in-memory fallback")
            return False

        try:
            import redis.asyncio as aioredis

            self._redis_client = aioredis.from_url(
                self._redis_url,
                decode_responses=False,
                socket_connect_timeout=5,
            )
            # Ping to verify connectivity
            await self._redis_client.ping()
            self._redis_available = True

            # Start Pub/Sub listener
            self._pubsub = self._redis_client.pubsub()
            self._listener_task = asyncio.create_task(
                self._redis_listener(),
                name="redis-broadcaster-listener",
            )
            logger.info("Redis broadcaster connected to %s", self._redis_url)
            return True

        except ImportError:
            logger.warning("redis package not installed — using in-memory fallback")
            return False
        except Exception as exc:
            logger.warning("Redis connection failed (%s) — using in-memory fallback", exc)
            self._redis_client = None
            self._pubsub = None
            self._redis_available = False
            return False

    async def disconnect(self) -> None:
        """Clean up Redis connections and background tasks."""
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        if self._pubsub is not None:
            try:
                await self._pubsub.close()
            except Exception as exc:
                logger.debug("Error closing pubsub: %s", exc)

        if self._redis_client is not None:
            try:
                await self._redis_client.close()
            except Exception as exc:
                logger.debug("Error closing redis client: %s", exc)

        self._redis_available = False
        logger.info("Redis broadcaster disconnected")

    def is_redis_available(self) -> bool:
        """Return ``True`` if Redis is currently connected."""
        return self._redis_available

    # ------------------------------------------------------------------
    # Publish / Subscribe
    # ------------------------------------------------------------------

    async def publish(self, room_id: str, message: bytes, *, deliver_local: bool = True) -> None:
        """Publish *message* to all subscribers of *room_id*.

        If Redis is available, the message is published to the Redis
        channel.  By default, the message is also delivered to local
        in-memory subscribers.

        Args:
            room_id: The room / workflow identifier.
            message: Binary payload to broadcast.
        """
        channel = _CHANNEL_PREFIX + room_id

        if deliver_local:
            await self._deliver_local(room_id, message)

        # Also publish to Redis if available
        if self._redis_available and self._redis_client is not None:
            try:
                await self._redis_client.publish(channel, message)
            except Exception as exc:
                logger.warning("Redis publish failed for %s: %s", room_id, exc)

    async def subscribe(
        self,
        room_id: str,
        callback: Callable[[bytes], Any],
    ) -> None:
        """Subscribe *callback* to messages in *room_id*.

        Args:
            room_id: The room / workflow identifier.
            callback: A callable that accepts a single ``bytes`` argument.
        """
        # Always register locally
        async with self._memory_lock:
            callbacks = self._memory_subs.setdefault(room_id, [])
            if callback not in callbacks:
                callbacks.append(callback)

        # Also subscribe to Redis channel if available
        if self._redis_available and self._pubsub is not None:
            channel = _CHANNEL_PREFIX + room_id
            try:
                await self._pubsub.subscribe(channel)
                logger.debug("Subscribed to Redis channel %s", channel)
            except Exception as exc:
                logger.warning("Redis subscribe failed for %s: %s", room_id, exc)

    async def unsubscribe(self, room_id: str) -> None:
        """Unsubscribe all local callbacks for *room_id*.

        Args:
            room_id: The room / workflow identifier.
        """
        async with self._memory_lock:
            self._memory_subs.pop(room_id, None)

        if self._redis_available and self._pubsub is not None:
            channel = _CHANNEL_PREFIX + room_id
            try:
                await self._pubsub.unsubscribe(channel)
                logger.debug("Unsubscribed from Redis channel %s", channel)
            except Exception as exc:
                logger.debug("Redis unsubscribe failed for %s: %s", room_id, exc)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _deliver_local(self, room_id: str, message: bytes) -> None:
        """Deliver *message* to all local subscribers of *room_id*."""
        async with self._memory_lock:
            callbacks = list(self._memory_subs.get(room_id, []))

        for cb in callbacks:
            try:
                result = cb(message)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                logger.warning("Error in broadcast callback for %s: %s", room_id, exc)

    async def _redis_listener(self) -> None:
        """Background task that listens for Redis Pub/Sub messages."""
        if self._pubsub is None:
            return

        try:
            async for msg in self._pubsub.listen():
                if msg is None:
                    continue
                if msg["type"] == "message":
                    channel: bytes = msg["channel"]
                    data: bytes = msg["data"]
                    # Extract room_id from channel name
                    channel_str = (
                        channel.decode("utf-8")
                        if isinstance(channel, bytes)
                        else str(channel)
                    )
                    if channel_str.startswith(_CHANNEL_PREFIX):
                        room_id = channel_str[len(_CHANNEL_PREFIX) :]
                        await self._deliver_local(room_id, data)

        except asyncio.CancelledError:
            logger.debug("Redis listener cancelled")
        except Exception as exc:
            logger.warning("Redis listener error: %s", exc)
            self._redis_available = False
