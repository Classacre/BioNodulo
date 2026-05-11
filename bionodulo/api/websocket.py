"""WebSocket endpoint for real-time execution updates.

Subscribes to EventHub and broadcasts events as JSON to connected clients.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from bionodulo.core.events import EventHub

logger = logging.getLogger(__name__)

websocket_router = APIRouter()


@websocket_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time execution event streaming.

    Connects to the EventHub and forwards events as JSON messages.
    Handles client ping/pong for connection health checks.
    """
    await websocket.accept()

    # Access event_hub from app state
    event_hub: EventHub = websocket.app.state.event_hub
    sub_id = ""

    try:
        sub_id = await event_hub.subscribe(filter_prefix="")
        queue = event_hub._subscribers.get(sub_id)
        if queue is None:
            await websocket.close(code=1011, reason="Failed to create subscription")
            return

        await websocket.send_json({"type": "connected", "data": {}})

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                message: dict[str, Any] = {
                    "type": event.type,
                    "data": event.data,
                    "source": event.source,
                    "event_id": event.event_id,
                }
                await websocket.send_json(message)
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_json({"type": "ping", "data": {}})
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected")
    except Exception as exc:
        logger.warning("WebSocket error: %s", exc)
    finally:
        if sub_id:
            await event_hub.unsubscribe(sub_id)
        try:
            await websocket.close()
        except Exception:
            pass
