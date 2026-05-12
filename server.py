"""FastAPI app factory for BioNodulo v2."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from bionodulo.api.routes import router
from bionodulo.api.websocket import websocket_router
from bionodulo.core.config import Settings, SettingsManager
from bionodulo.core.events import EventHub
from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.execution.queue import RunQueue
from bionodulo.nodes.registry import NodeRegistry


def create_app() -> FastAPI:
    app = FastAPI(
        title="BioNodulo",
        description="Visual bioinformatics workflow engine",
        version="Alpha 1.1",
    )

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
    )
    run_queue = RunQueue(
        executor=executor,
        max_concurrent=settings.execution.max_workers,
        emit=event_hub.emit,
    )

    # Settings manager
    settings_manager = SettingsManager(settings.settings_file)

    # Store on app state
    app.state.settings = settings
    app.state.node_registry = registry
    app.state.run_queue = run_queue
    app.state.event_hub = event_hub
    app.state.settings_manager = settings_manager

    @app.on_event("startup")
    async def startup() -> None:
        pass  # RunQueue worker auto-starts on first submit

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await run_queue.shutdown()

    # Include routers
    app.include_router(router, prefix="/api")
    app.include_router(websocket_router)

    # Static files (frontend)
    web_dist = Path(__file__).parent / "web" / "dist"
    if web_dist.exists():
        app.mount("/assets", StaticFiles(directory=web_dist / "assets"), name="assets")

        @app.get("/{path:path}")
        async def serve_spa(request: Request, path: str) -> FileResponse:
            # API paths should be handled by routers above
            if path.startswith("object_info") or path.startswith("api/") or path.startswith("workspace/") or path.startswith("manager/") or path.startswith("workflow/") or path.startswith("runs") or path.startswith("queue") or path.startswith("history") or path.startswith("config/") or path.startswith("ai/") or path.startswith("settings") or path.startswith("hpc/") or path.startswith("docs/") or path.startswith("workflow_templates") or path.startswith("i18n"):
                # Let the router handle it
                from fastapi.exceptions import HTTPException
                raise HTTPException(status_code=404, detail="Not found")
            index_file = web_dist / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            return PlainTextResponse("Frontend not built. Run 'cd web && npm run build'.", status_code=404)

    return app


# For uvicorn factory pattern
app = create_app()
