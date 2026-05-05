from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bionodulo.api.routes import router
from bionodulo.api.websocket import websocket_router
from bionodulo.core.config import Settings
from bionodulo.execution.queue import RunQueue
from bionodulo.nodes.registry import NodeRegistry


def create_app() -> FastAPI:
    settings = Settings.from_env()
    registry = NodeRegistry()
    registry.load_builtin_nodes()
    registry.load_custom_nodes(settings.custom_nodes_dir)
    run_queue = RunQueue(settings=settings, registry=registry)

    app = FastAPI(title="BioNodulo", version="0.1.0")
    app.state.settings = settings
    app.state.node_registry = registry
    app.state.run_queue = run_queue

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    app.include_router(websocket_router)

    web_dir = Path(__file__).parent / "web"
    app.mount("/static", StaticFiles(directory=web_dir), name="static")

    @app.on_event("startup")
    async def _startup() -> None:
        settings.ensure_directories()
        await run_queue.start()

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await run_queue.stop()

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(web_dir / "index.html")

    return app


app = create_app()
