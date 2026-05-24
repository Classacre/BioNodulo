"""FastAPI app factory for BioNodulo v2."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from slowapi.extension import _rate_limit_exceeded_handler

from bionodulo.api.rate_limits import RateLimitExceeded, SlowAPIMiddleware, limiter
from bionodulo.api.routes import router
from bionodulo.api.ai_routes import ai_router
from bionodulo.api.auth_routes import auth_router
from bionodulo.api.collab_runtime_routes import collab_runtime_router
from bionodulo.api.settings_routes import settings_router
from bionodulo.api.websocket import websocket_router
from bionodulo.api.collab_routes import collab_api_router
from bionodulo.collab.yjs_native_handler import stop_room_cache_cleanup, yjs_router
from bionodulo.collab.heartbeat import HeartbeatManager
from bionodulo.collab.redis_broadcaster import RedisBroadcaster
from bionodulo.core.config import Settings, SettingsManager
from bionodulo.core.events import EventHub
from bionodulo.core.workspace import ensure_examples_link, ensure_workspace_root
from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.execution.queue import RunQueue
from bionodulo.nodes.registry import NodeRegistry

_COLLAB_WORKFLOW_ID_RE = re.compile(r"^[a-zA-Z0-9._:-]{1,160}$")


def _default_collab_workflow() -> str | None:
    """Return the configured shared room for single-link notebook launches."""
    workflow_id = os.environ.get("BIONODULO_COLLAB_DEFAULT_WORKFLOW", "").strip()
    if workflow_id and _COLLAB_WORKFLOW_ID_RE.fullmatch(workflow_id):
        return workflow_id
    return None


def create_app() -> FastAPI:
    project_dir = Path(__file__).resolve().parent
    workspace_root = ensure_workspace_root(project_dir)
    ensure_examples_link(workspace_root, project_dir)

    app = FastAPI(
        title="BioNodulo",
        description="Visual bioinformatics workflow engine",
        version="0.1.5",
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Load settings
    settings = Settings.from_env()
    settings.ensure_directories()

    # Node registry
    registry = NodeRegistry()
    registry.load_builtin_nodes()
    registry.load_custom_nodes(settings.custom_nodes_dir)

    # Event hub (must be created before run_queue for emit callback)
    event_hub = EventHub()

    # Run queue
    executor = WorkflowExecutor(
        workspace_dir=settings.project_root,
        cache_dir=settings.cache_dir,
        registry=registry,
        settings=settings,
    )

    def _emit_to_hub(event_type: str, data: dict[str, Any]) -> None:
        asyncio.create_task(event_hub.emit_typed(event_type, data))

    run_queue = RunQueue(
        executor=executor,
        max_concurrent=settings.execution.max_workers,
        emit=_emit_to_hub,
    )

    # Settings manager
    settings_manager = SettingsManager(settings.settings_file)

    # Store on app state
    app.state.settings = settings
    app.state.node_registry = registry
    app.state.run_queue = run_queue
    app.state.event_hub = event_hub
    app.state.settings_manager = settings_manager
    app.state.room_manager = None  # lazily created by collab module

    # Collaboration infrastructure
    app.state.heartbeat_manager = HeartbeatManager()
    app.state.rate_limiter = None  # lazily created by collab module
    app.state.redis_broadcaster = RedisBroadcaster()

    # Native Yjs room sockets (workflow_id -> list of WebSockets)
    app.state.yjs_room_sockets = {}

    @app.on_event("startup")
    async def startup() -> None:
        # Note: pixi installation is surfaced via /api/host_status
        # and handled by the frontend so the user is aware of it.
        # RunQueue worker auto-starts on first submit

        # Connect to Redis (falls back to in-memory if unavailable)
        try:
            await app.state.redis_broadcaster.connect()
        except Exception:
            # Already logged inside connect()
            pass

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await run_queue.shutdown()

        # Shut down heartbeat manager
        try:
            await app.state.heartbeat_manager.shutdown()
        except Exception as exc:
            logger = __import__("logging").getLogger(__name__)
            logger.warning("Error shutting down heartbeat manager: %s", exc)

        # Disconnect Redis
        try:
            await app.state.redis_broadcaster.disconnect()
        except Exception as exc:
            logger = __import__("logging").getLogger(__name__)
            logger.warning("Error disconnecting Redis broadcaster: %s", exc)

        try:
            await stop_room_cache_cleanup()
        except Exception as exc:
            logger = __import__("logging").getLogger(__name__)
            logger.warning("Error stopping Yjs room cleanup: %s", exc)

    # Include routers
    app.include_router(router, prefix="/api")
    app.include_router(settings_router, prefix="/api")
    app.include_router(ai_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(collab_runtime_router, prefix="/api")
    app.include_router(collab_api_router, prefix="/api")
    app.include_router(websocket_router)
    app.include_router(yjs_router)

    # Static files (frontend)
    web_dist = Path(__file__).parent / "web" / "dist"
    web_assets = web_dist / "assets"
    if web_dist.exists():
        if web_assets.exists():
            app.mount("/assets", StaticFiles(directory=web_assets), name="assets")

        @app.get("/{path:path}")
        async def serve_spa(request: Request, path: str) -> Response:
            # API paths should be handled by routers above
            _api_prefixes = frozenset({
                "object_info", "api", "workspace", "manager", "workflow",
                "runs", "queue", "history", "config", "ai", "settings",
                "hpc", "docs", "workflow_templates", "i18n",
            })
            if any(path.startswith(p) or path.startswith(p + "/") for p in _api_prefixes):
                # Let the router handle it
                from fastapi.exceptions import HTTPException
                raise HTTPException(status_code=404, detail="Not found")
            default_workflow = _default_collab_workflow()
            if not path and default_workflow and not request.query_params.get("workflow"):
                return RedirectResponse(
                    str(request.url.include_query_params(workflow=default_workflow)),
                    status_code=307,
                )
            index_file = web_dist / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            return PlainTextResponse("Frontend not built. Run 'cd web && npm run build'.", status_code=404)

    return app


# For uvicorn factory pattern
app = create_app()
