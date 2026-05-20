"""Server-side WebSocket heartbeat (ping / pong) health monitor.

Each connected WebSocket is registered with a :class:`HeartbeatManager`
that periodically sends *ping* frames and expects a *pong* response
within a timeout. If the client fails to respond, the connection is
closed from the server side.

The manager uses asyncio background tasks — one per registered websocket.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)

# Default timing constants (seconds)
DEFAULT_PING_INTERVAL = 30.0
DEFAULT_PONG_TIMEOUT = 10.0


class HeartbeatManager:
    """Manages per-WebSocket ping/pong health checks.

    Usage::

        hb = HeartbeatManager(ping_interval=30, pong_timeout=10)
        hb.register(websocket)
        # ... later on disconnect ...
        hb.unregister(websocket)
    """

    def __init__(
        self,
        ping_interval: float = DEFAULT_PING_INTERVAL,
        pong_timeout: float = DEFAULT_PONG_TIMEOUT,
    ) -> None:
        self.ping_interval = ping_interval
        self.pong_timeout = pong_timeout
        # websocket -> {"task": Task, "alive": bool, "lock": Lock}
        self._registrations: dict[WebSocket, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, websocket: WebSocket) -> None:
        """Start a ping loop for *websocket*."""
        if websocket in self._registrations:
            logger.debug("Heartbeat already registered for %s", id(websocket))
            return

        lock = asyncio.Lock()
        info = {
            "task": None,
            "alive": True,
            "lock": lock,
        }
        self._registrations[websocket] = info
        info["task"] = asyncio.create_task(
            self._ping_loop(websocket),
            name=f"heartbeat-{id(websocket)}",
        )
        logger.debug("Heartbeat registered for websocket %s", id(websocket))

    def unregister(self, websocket: WebSocket) -> None:
        """Stop the ping loop for *websocket* and clean up."""
        info = self._registrations.pop(websocket, None)
        if info is None:
            return
        task = info.get("task")
        if task and not task.done():
            task.cancel()
        logger.debug("Heartbeat unregistered for websocket %s", id(websocket))

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def is_alive(self, websocket: WebSocket) -> bool:
        """Return ``True`` if the websocket has responded to the last ping."""
        info = self._registrations.get(websocket)
        if info is None:
            return False
        return info["alive"]

    def on_pong(self, websocket: WebSocket) -> None:
        """Mark *websocket* as alive (call this when a pong frame arrives)."""
        info = self._registrations.get(websocket)
        if info is not None:
            info["alive"] = True
            logger.debug("Pong received from websocket %s", id(websocket))

    # ------------------------------------------------------------------
    # Background ping loop
    # ------------------------------------------------------------------

    async def _ping_loop(self, websocket: WebSocket) -> None:
        """Periodically ping *websocket* and close it if unresponsive."""
        info = self._registrations.get(websocket)
        if info is None:
            return

        try:
            while True:
                await asyncio.sleep(self.ping_interval)

                # Check websocket is still open before pinging
                if websocket.client_state == WebSocketState.DISCONNECTED:
                    logger.debug("Websocket %s disconnected, stopping heartbeat", id(websocket))
                    break

                # Reset alive flag before sending ping
                info["alive"] = False

                try:
                    await websocket.send_bytes(b"\x00")  # ping marker
                except Exception as exc:
                    logger.debug("Failed to send ping to %s: %s", id(websocket), exc)
                    break

                # Wait for pong response
                try:
                    await asyncio.wait_for(
                        self._wait_for_pong(websocket),
                        timeout=self.pong_timeout,
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "Pong timeout for websocket %s — closing connection",
                        id(websocket),
                    )
                    try:
                        await websocket.close(code=1001, reason="Heartbeat timeout")
                    except Exception:
                        pass
                    break

        except asyncio.CancelledError:
            logger.debug("Heartbeat task cancelled for websocket %s", id(websocket))
        except Exception as exc:
            logger.debug("Heartbeat loop error for websocket %s: %s", id(websocket), exc)
        finally:
            self._registrations.pop(websocket, None)

    async def _wait_for_pong(self, websocket: WebSocket) -> None:
        """Poll until the alive flag is set (by ``on_pong``) or the websocket dies."""
        info = self._registrations.get(websocket)
        if info is None:
            raise asyncio.CancelledError()

        while not info["alive"]:
            # Check if the websocket has been unregistered or disconnected
            if websocket not in self._registrations:
                raise asyncio.CancelledError()
            if websocket.client_state == WebSocketState.DISCONNECTED:
                raise asyncio.CancelledError()
            await asyncio.sleep(0.5)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def shutdown(self) -> None:
        """Cancel all heartbeat tasks (called on application shutdown)."""
        tasks: list[asyncio.Task[Any]] = []
        for info in self._registrations.values():
            task = info.get("task")
            if task and not task.done():
                task.cancel()
                tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self._registrations.clear()
        logger.info("HeartbeatManager shut down (%d tasks cancelled)", len(tasks))

    def active_count(self) -> int:
        """Return the number of actively monitored connections."""
        return len(self._registrations)
