"""FastAPI app factory for BioNodulo v2."""

from __future__ import annotations

import asyncio
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
    # Default workspace to project_dir/workspace if not overridden
    if "BIONODULO_ROOT" not in os.environ:
        project_dir = Path(__file__).resolve().parent
        default_root = (project_dir / "workspace").resolve()
        # Many bioinformatics tools cannot handle spaces in paths.
        # Use a space-free fallback under the home directory.
        if " " in str(default_root):
            default_root = (Path.home() / ".bionodulo" / "workspace").resolve()
        os.environ["BIONODULO_ROOT"] = str(default_root)
        # Symlink examples into the workspace so templates can resolve them
        examples_src = project_dir / "examples"
        examples_dst = default_root / "examples"
        if examples_src.exists() and not examples_dst.exists():
            default_root.mkdir(parents=True, exist_ok=True)
            os.symlink(str(examples_src), str(examples_dst))

    app = FastAPI(
        title="BioNodulo",
        description="Visual bioinformatics workflow engine",
        version="0.1.3",
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

    @app.on_event("startup")
    async def startup() -> None:
        # Note: pixi installation is surfaced via /api/host_status
        # and handled by the frontend so the user is aware of it.
        # RunQueue worker auto-starts on first submit
        pass

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
            _api_prefixes = frozenset({
                "object_info", "api", "workspace", "manager", "workflow",
                "runs", "queue", "history", "config", "ai", "settings",
                "hpc", "docs", "workflow_templates", "i18n",
            })
            if any(path.startswith(p) or path.startswith(p + "/") for p in _api_prefixes):
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
