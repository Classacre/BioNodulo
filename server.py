"""FastAPI app factory for BioNodulo v2."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send
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
from bionodulo.execution.run_store import RunStore
from bionodulo.nodes.registry import NodeRegistry

logger = logging.getLogger(__name__)

_PREFIX_ROUTE_MARKERS = ("/api/", "/assets/", "/ws/")
_PREFIX_EXACT_ROUTES = frozenset({"/api", "/assets", "/ws"})
_SPA_API_PREFIXES = frozenset({
    "object_info", "api", "workspace", "manager", "workflow",
    "runs", "queue", "history", "config", "ai", "settings",
    "hpc", "docs", "workflow_templates", "i18n",
})


class ProxyPrefixMiddleware:
    """Strip notebook/proxy path prefixes before FastAPI routing.

    Colab-like hosted URLs can expose the app below a path such as
    /proxy/8000/. The browser must request assets, API calls, and WebSockets
    under that visible prefix, but BioNodulo's routers are mounted at /assets,
    /api, and /ws. Normalising the ASGI scope here keeps the public URL stable
    without duplicating every backend route.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in {"http", "websocket"}:
            path = str(scope.get("path", ""))
            normalised = self._normalise_path(path)
            if normalised != path:
                scope = dict(scope)
                scope["path"] = normalised
        await self.app(scope, receive, send)

    @staticmethod
    def _normalise_path(path: str) -> str:
        if path in _PREFIX_EXACT_ROUTES:
            return path
        for route in _PREFIX_EXACT_ROUTES:
            if path.endswith(route):
                prefix = path[: -len(route)]
                if prefix:
                    return route
        for marker in _PREFIX_ROUTE_MARKERS:
            index = path.find(marker)
            if index > 0:
                return path[index:]
        return path


@asynccontextmanager
async def _app_lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Pixi installation is surfaced via /api/host_status and handled by the
    # frontend. RunQueue workers still auto-start on first submit.
    redis_broadcaster = app.state.redis_broadcaster
    try:
        await redis_broadcaster.connect()
    except Exception as exc:
        logger.warning("Error connecting Redis broadcaster: %s", exc)

    try:
        yield
    finally:
        run_queue: RunQueue = app.state.run_queue
        await run_queue.shutdown()

        dependency_installer = getattr(app.state, "dependency_installer", None)
        if dependency_installer is not None:
            try:
                await dependency_installer.shutdown()
            except Exception as exc:
                logger.warning("Error shutting down dependency installer: %s", exc)

        hpc_backend = getattr(app.state, "hpc_backend", None)
        if hpc_backend is not None and hasattr(hpc_backend, "shutdown"):
            try:
                await hpc_backend.shutdown()
            except Exception as exc:
                logger.warning("Error shutting down HPC backend: %s", exc)

        try:
            await app.state.heartbeat_manager.shutdown()
        except Exception as exc:
            logger.warning("Error shutting down heartbeat manager: %s", exc)

        try:
            await redis_broadcaster.disconnect()
        except Exception as exc:
            logger.warning("Error disconnecting Redis broadcaster: %s", exc)

        tunnel_process = getattr(app.state, "collab_tunnel_process", None)
        if tunnel_process is not None and tunnel_process.returncode is None:
            tunnel_process.terminate()
            try:
                await asyncio.wait_for(tunnel_process.wait(), timeout=3)
            except Exception:
                tunnel_process.kill()

        try:
            await stop_room_cache_cleanup()
        except Exception as exc:
            logger.warning("Error stopping Yjs room cleanup: %s", exc)


def create_app() -> FastAPI:
    project_dir = Path(__file__).resolve().parent
    workspace_root = ensure_workspace_root(project_dir)
    ensure_examples_link(workspace_root, project_dir)

    app = FastAPI(
        title="BioNodulo",
        description="Visual bioinformatics workflow engine",
        version="0.1.5",
        lifespan=_app_lifespan,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(ProxyPrefixMiddleware)

    # CORS. A wildcard origin with credentials lets any website drive the API
    # via the user's browser, so honor --cors-origins (BIONODULO_CORS_ORIGINS)
    # and default to same-origin + local dev origins rather than "*".
    cors_env = os.environ.get("BIONODULO_CORS_ORIGINS", "").strip()
    if cors_env and cors_env != "*":
        cors_origins = [origin.strip() for origin in cors_env.split(",") if origin.strip()]
        cors_allow_credentials = True
    elif cors_env == "*":
        # Explicit opt-in to a wide-open API: browsers forbid "*" + credentials,
        # so credentials are disabled in that mode.
        cors_origins = ["*"]
        cors_allow_credentials = False
    else:
        host = os.environ.get("BIONODULO_HOST", "127.0.0.1")
        port = os.environ.get("BIONODULO_PORT", "8000")
        cors_origins = [
            f"http://{host}:{port}",
            f"http://localhost:{port}",
            f"http://127.0.0.1:{port}",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
        cors_allow_credentials = True
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=cors_allow_credentials,
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
        task = asyncio.create_task(event_hub.emit_typed(event_type, data))

        def _log_emit_error(done: asyncio.Task[None]) -> None:
            try:
                done.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Unhandled event hub emit failure")

        task.add_done_callback(_log_emit_error)

    # Settings manager
    settings_manager = SettingsManager(settings.settings_file)

    # Bridge user-facing execution settings (settings_manager) onto the config
    # ExecutionSettings that the executor + queue actually read. Applied at
    # startup; in-place mutation so the already-built executor (same settings
    # object) picks them up. Changing these takes effect on next restart.
    def _user_setting(key: str) -> Any:
        try:
            return settings_manager.get(key)
        except Exception:
            return None

    _ex = settings.execution
    _mw = _user_setting("bionodulo.execution.maxWorkers")
    if _mw is not None:
        try:
            _ex.max_workers = max(1, int(_mw))
        except (TypeError, ValueError):
            pass
    _ch = _user_setting("bionodulo.execution.contentHashing")
    if _ch in ("fast", "strong", "off"):
        _ex.content_hashing = _ch
    _ei = _user_setting("bionodulo.execution.envIsolation")
    if _ei in ("auto", "always", "off"):
        _ex.env_isolation = _ei
    _ts = _user_setting("bionodulo.execution.timeoutSeconds")
    if _ts is not None:
        try:
            _ex.timeout_seconds = max(1, int(_ts))
        except (TypeError, ValueError):
            pass

    try:
        _history_cap = int(settings_manager.get("bionodulo.queueHistorySize") or 100)
    except (TypeError, ValueError):
        _history_cap = 100

    # Durable run store so the queue survives restarts: pending/running runs are
    # persisted and reconciled on startup (orphans marked interrupted).
    try:
        run_store: RunStore | None = RunStore(settings.project_root / "runs" / "runs.db")
    except Exception:
        logger.exception("Failed to open run store; running without persistence")
        run_store = None

    run_queue = RunQueue(
        executor=executor,
        max_concurrent=settings.execution.max_workers,
        emit=_emit_to_hub,
        max_history=_history_cap,
        store=run_store,
    )
    if run_store is not None:
        try:
            summary = run_queue.recover()
            if summary.get("interrupted") or summary.get("restored"):
                logger.info(
                    "Run store recovery: %d restored, %d interrupted",
                    summary.get("restored", 0),
                    len(summary.get("interrupted", [])),
                )
        except Exception:
            logger.exception("Run store recovery failed")

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
    # Temporary invite-token rooms. Process-local by design: links expire when
    # the host app stops, matching the local/Colab collaboration model.
    app.state.collab_temporary_invites = {}
    app.state.collab_public_url = None
    app.state.collab_tunnel_process = None
    app.state.collab_tunnel_provider = None

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
        index_file = web_dist / "index.html"
        frontend_build_complete = index_file.exists() and web_assets.exists()
        if web_assets.exists():
            app.mount("/assets", StaticFiles(directory=web_assets), name="assets")

        @app.get("/{path:path}")
        async def serve_spa(request: Request, path: str) -> Response:
            # API paths should be handled by routers above
            if any(path.startswith(p) or path.startswith(p + "/") for p in _SPA_API_PREFIXES):
                # Let the router handle it
                raise HTTPException(status_code=404, detail="Not found")
            if path == "assets" or path.startswith("assets/"):
                raise HTTPException(
                    status_code=404,
                    detail="Frontend assets are missing. Run 'cd web && npm run build'.",
                )
            if index_file.exists() and not frontend_build_complete:
                return PlainTextResponse(
                    "Frontend build incomplete: web/dist/assets is missing. "
                    "Run 'cd web && npm run build' before starting BioNodulo.",
                    status_code=503,
                )
            if frontend_build_complete:
                return FileResponse(index_file)
            return PlainTextResponse("Frontend not built. Run 'cd web && npm run build'.", status_code=404)

    return app


# For uvicorn factory pattern
app = create_app()
