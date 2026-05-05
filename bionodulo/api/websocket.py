from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from bionodulo.core.events import event_hub

websocket_router = APIRouter()


@websocket_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = event_hub.subscribe()
    try:
        await websocket.send_json({"type": "status", "data": {"connected": True}})
        while True:
            event = await queue.get()
            await websocket.send_json(event.as_dict())
    except WebSocketDisconnect:
        pass
    finally:
        event_hub.unsubscribe(queue)
