"""FastAPI app factory for BioNodulo v2."""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
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
from bionodulo.core.config import CloudSettings, Settings, SettingsManager
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


class SessionTokenMiddleware:
    """Reject requests that don't carry the per-session cloud token.

    When the app is cloud-launched (``BIONODULO_SESSION_TOKEN`` is set), the
    only legitimate traffic arrives through the cloud reverse proxy, which
    injects ``X-Bionodulo-Session: <token>`` on every forwarded request
    (including static assets). Direct hits to the task's public IP carry no such
    header, so we 401 them. This sits inside ProxyPrefixMiddleware so it reads
    the normalised path.

    Exemptions:
      - ``/api/health`` — the ECS container health check calls it locally with
        no header and MUST stay open.

    When the env var is unset (local / self-host), the gate is a no-op.
    """

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # M8 (audit): gate HTTP *and* WebSocket. Collab sockets carry the same
        # X-Bionodulo-Session header on the upgrade request, so an ungated WS
        # scope would let a direct connection bypass the proxy gate.
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path", ""))
        if scope["type"] == "http" and path == "/api/health":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        provided = headers.get(b"x-bionodulo-session", b"").decode("latin-1")
        if not secrets.compare_digest(provided, self.token):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            response = PlainTextResponse("Unauthorized", status_code=401)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


# C2 (audit): in shared-editor mode the app is a stateless, multi-tenant
# backend that must NEVER load or mutate code. These request path prefixes reach
# routes that upload/reload/install/remove custom nodes (ultimately
# registry.load_custom_nodes -> exec_module) or run/queue jobs, so they are
# hard-blocked at the ASGI layer regardless of any router wiring. Paths are the
# normalised, /api-prefixed form (this runs after ProxyPrefixMiddleware).
_EDITOR_FORBIDDEN_PREFIXES = (
    "/api/workspace/upload",
    "/api/workspace/delete",
    "/api/workspace/file-operation",
    "/api/manager/reload",
    "/api/manager/install-git",
    "/api/manager/update",
    "/api/manager/remove",
    "/api/cache/clear",
    "/api/hpc",
)


def _is_editor_forbidden(path: str) -> bool:
    for prefix in _EDITOR_FORBIDDEN_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False


class EditorLockdownMiddleware:
    """Block code-loading / mutating routes in shared-editor mode (audit C2).

    The main API router (with /workspace/upload, /manager/reload, /manager/*,
    /workspace/delete, /cache/clear, /hpc/*) is mounted unconditionally, but in
    editor mode the process is shared and multi-tenant: reaching any of those
    routes is an authenticated RCE (upload -> reload -> exec_module) or lets one
    tenant mutate shared state. Rather than rewire every router, we reject the
    forbidden prefixes here with 403. Added only when editor_mode is true.

    Sits inside ProxyPrefixMiddleware (added before it) so it reads the
    normalised path and can't be bypassed with a proxy prefix.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in {"http", "websocket"} and _is_editor_forbidden(
            str(scope.get("path", ""))
        ):
            if scope["type"] == "websocket":
                # Reject the handshake outright.
                await send({"type": "websocket.close", "code": 1008})
                return
            response = PlainTextResponse(
                "This endpoint is disabled in editor mode", status_code=403
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class ProxySecretMiddleware:
    """Gate the shared editor backend behind a single shared proxy secret.

    In shared-editor mode the app is stateless and multi-tenant: legitimate
    traffic only arrives through the website's reverse proxy, which injects
    ``X-Bionodulo-Session: <proxy_secret>``. Direct public hits are 401'd.
    ``/api/health`` (load-balancer health check) and ``/api/config`` (the SPA
    reads it before anything else) are exempt.
    """

    def __init__(self, app: ASGIApp, secret: str) -> None:
        self.app = app
        self.secret = secret

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # M8 (audit): gate HTTP *and* WebSocket. Collab/Yjs sockets present the
        # proxy secret on the upgrade request; an ungated WS scope would let a
        # direct connection to the task bypass the shared-editor gate.
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        path = str(scope.get("path", ""))
        if scope["type"] == "http" and path in ("/api/health", "/api/config"):
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        provided = headers.get(b"x-bionodulo-session", b"").decode("latin-1")
        if not secrets.compare_digest(provided, self.secret):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            response = PlainTextResponse("Unauthorized", status_code=401)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


@asynccontextmanager
async def _app_lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Pixi installation is surfaced via /api/host_status and handled by the
    # frontend. RunQueue workers still auto-start on first submit.
    # In shared-editor mode the run/collab infrastructure is not created, so all
    # of these are guarded with None checks.
    redis_broadcaster = getattr(app.state, "redis_broadcaster", None)
    if redis_broadcaster is not None:
        try:
            await redis_broadcaster.connect()
        except Exception as exc:
            logger.warning("Error connecting Redis broadcaster: %s", exc)

    try:
        yield
    finally:
        run_queue: RunQueue | None = getattr(app.state, "run_queue", None)
        if run_queue is not None:
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

        heartbeat_manager = getattr(app.state, "heartbeat_manager", None)
        if heartbeat_manager is not None:
            try:
                await heartbeat_manager.shutdown()
            except Exception as exc:
                logger.warning("Error shutting down heartbeat manager: %s", exc)

        if redis_broadcaster is not None:
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
    # In shared-editor mode the process is stateless and may run on a read-only
    # filesystem (AWS Lambda): skip workspace/examples setup entirely. Writable
    # scratch (cache/runs) lives under BIONODULO_ROOT (point it at /tmp).
    editor_mode = os.environ.get("BIONODULO_EDITOR_MODE", "").strip().lower() in (
        "1", "true", "yes", "on",
    )
    project_dir = Path(__file__).resolve().parent
    if not editor_mode:
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

    # Cloud-launch identity + per-session token (read from BIONODULO_* env).
    cloud_settings = CloudSettings.from_env()
    app.state.cloud_settings = cloud_settings
    editor_mode = cloud_settings.editor_mode
    # Request gate (added before ProxyPrefixMiddleware so it runs AFTER path
    # normalisation — last-added middleware is outermost — and matches the
    # canonical exempt paths regardless of any proxy prefix):
    #   - shared-editor mode -> ProxySecretMiddleware (one shared secret)
    #   - per-session cloud   -> SessionTokenMiddleware (per-user token)
    if editor_mode and cloud_settings.proxy_secret:
        app.add_middleware(
            ProxySecretMiddleware, secret=cloud_settings.proxy_secret
        )
    elif editor_mode and not cloud_settings.proxy_secret:
        # FAIL-CLOSED: a shared, multi-tenant editor backend must never run
        # without its request gate. Refuse to boot rather than silently serving
        # the editing API ungated. Local dev can opt out explicitly.
        allow_insecure = os.environ.get(
            "BIONODULO_ALLOW_INSECURE_EDITOR", ""
        ).strip().lower() in ("1", "true", "yes", "on")
        if not allow_insecure:
            raise RuntimeError(
                "BIONODULO_EDITOR_MODE is set but BIONODULO_PROXY_SECRET is empty. "
                "The shared editor backend refuses to run ungated. Set "
                "BIONODULO_PROXY_SECRET, or BIONODULO_ALLOW_INSECURE_EDITOR=1 for "
                "local development only."
            )
        logger.warning(
            "Editor mode running WITHOUT a proxy secret "
            "(BIONODULO_ALLOW_INSECURE_EDITOR set) — do NOT use in production."
        )
    elif cloud_settings.session_token:
        app.add_middleware(
            SessionTokenMiddleware, token=cloud_settings.session_token
        )
    # C2 (audit): hard-block code-loading / mutating routes in editor mode. Added
    # after the request gate (so it runs before it) and before
    # ProxyPrefixMiddleware (so it runs on the normalised path). Forbidden paths
    # are 403'd whether or not the proxy secret is present — fail-closed.
    if editor_mode:
        app.add_middleware(EditorLockdownMiddleware)
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

    # H7 (audit): OPT-IN Host-header allowlist to defeat DNS-rebinding. The local
    # desktop backend binds 127.0.0.1 but, without a Host check, a malicious web
    # page can rebind a hostname it controls to 127.0.0.1:<port> and drive this
    # unauthenticated API from the victim's browser (submitting a workflow ==
    # local code execution).
    #
    # This is OPT-IN (default: no check) because the collab-tunnel feature
    # deliberately serves the app on an ARBITRARY public hostname assigned by the
    # tunnel provider (Cloudflare/ngrok), which a static allowlist cannot know in
    # advance. Enforcing by default would break that feature.
    #
    # Set BIONODULO_ALLOWED_HOSTS to enable:
    #   - a comma-separated host list  -> enforce that allowlist
    #   - the literal "localhost"      -> shorthand for the loopback set below
    #     (recommended for a local desktop install that does NOT use tunnels;
    #     the Electron shell can export this when it spawns the backend)
    # Leave unset (or "*") to allow any Host (current behaviour; required for
    # tunnels / reverse-proxied deployments that terminate Host upstream).
    allowed_hosts_env = os.environ.get("BIONODULO_ALLOWED_HOSTS", "").strip()
    if allowed_hosts_env and allowed_hosts_env != "*":
        if allowed_hosts_env.lower() == "localhost":
            _host = os.environ.get("BIONODULO_HOST", "127.0.0.1")
            _port = os.environ.get("BIONODULO_PORT", "8000")
            allowed_hosts = [
                "localhost",
                "127.0.0.1",
                "[::1]",
                f"localhost:{_port}",
                f"127.0.0.1:{_port}",
                f"{_host}:{_port}",
                _host,
                "testserver",  # Starlette TestClient default Host
            ]
        else:
            allowed_hosts = [
                h.strip() for h in allowed_hosts_env.split(",") if h.strip()
            ]
        allowed_hosts = list(dict.fromkeys(allowed_hosts))  # de-dup, keep order
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    # Load settings
    settings = Settings.from_env()
    settings.ensure_directories()

    # Node registry. In shared-editor mode we load BUILTINS ONLY — never load
    # arbitrary custom node code into the shared multi-tenant process.
    registry = NodeRegistry()
    registry.load_builtin_nodes()
    if not editor_mode:
        registry.load_custom_nodes(settings.custom_nodes_dir)

    # Event hub (must be created before run_queue for emit callback)
    event_hub = EventHub()
    # Settings manager (both modes)
    settings_manager = SettingsManager(settings.settings_file)

    # Common app state (both modes)
    app.state.settings = settings
    app.state.node_registry = registry
    app.state.event_hub = event_hub
    app.state.settings_manager = settings_manager
    app.state.room_manager = None  # lazily created by collab module
    app.state.rate_limiter = None  # lazily created by collab module

    if editor_mode:
        # Stateless shared editor backend: serve node schemas + the stateless
        # editing endpoints only. No run queue / executor / run store / collab /
        # redis / heartbeat — nothing per-user or that runs user workflows.
        app.state.run_queue = None
        app.state.redis_broadcaster = None
        app.state.heartbeat_manager = None
        app.state.yjs_room_sockets = {}
        app.state.collab_temporary_invites = {}
        app.state.collab_public_url = None
        app.state.collab_tunnel_process = None
        app.state.collab_tunnel_provider = None
    else:
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

        # Bridge user-facing execution settings (settings_manager) onto the
        # config ExecutionSettings that the executor + queue actually read.
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

        # Durable run store so the queue survives restarts.
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

        app.state.run_queue = run_queue

        # Collaboration infrastructure
        app.state.heartbeat_manager = HeartbeatManager()
        app.state.redis_broadcaster = RedisBroadcaster()
        # Native Yjs room sockets (workflow_id -> list of WebSockets)
        app.state.yjs_room_sockets = {}
        # Temporary invite-token rooms. Process-local by design.
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
