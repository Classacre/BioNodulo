#!/usr/bin/env python3
"""BioNodulo v2 entry point."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from bionodulo.core.workspace import default_workspace_root, ensure_workspace_root

try:
    import uvloop
except ImportError:
    uvloop = None  # type: ignore


def main() -> None:
    parser = argparse.ArgumentParser(description="BioNodulo - Visual bioinformatics pipelines")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    parser.add_argument("--project-root", type=Path, default=None, help="Project/workspace root directory")
    parser.add_argument("--config", type=Path, default=None, help="Path to config YAML file")
    parser.add_argument("--dev", action="store_true", help="Enable development mode with auto-reload")
    parser.add_argument("--frontend-dev", action="store_true", help="Proxy frontend from vite dev server")
    parser.add_argument("--tls-keyfile", type=Path, default=None, help="Path to TLS key file for HTTPS")
    parser.add_argument("--tls-certfile", type=Path, default=None, help="Path to TLS certificate file for HTTPS")
    parser.add_argument("--cors-origins", type=str, default="*", help="CORS allowed origins (comma-separated, default: *)")
    parser.add_argument("--multi-user", action="store_true", help="Enable per-user storage isolation")
    args = parser.parse_args()

    project_dir = Path(__file__).resolve().parent
    if args.project_root:
        os.environ["BIONODULO_ROOT"] = str(args.project_root.resolve())
    else:
        os.environ["BIONODULO_ROOT"] = str(default_workspace_root(project_dir))
    if args.config:
        os.environ["BIONODULO_CONFIG"] = str(args.config.resolve())

    # Ensure project root exists
    root = ensure_workspace_root(project_dir)

    # Install uvloop for faster asyncio event loop (2-4x I/O throughput)
    if uvloop is not None:
        uvloop.install()

    print(f"""
    =========================================
     BioNodulo v2
     Visual bioinformatics pipelines
    =========================================
     Host:    {args.host}:{args.port}
     Root:    {root}
     Mode:    real execution with isolated environments
    =========================================
    Open http://{args.host}:{args.port} in your browser
    """)

    ssl_kwargs: dict[str, str | int | bool | list[str] | None] = {
        "factory": True,
        "reload": args.dev,
        "reload_dirs": [str(Path(__file__).parent)] if args.dev else None,
        "log_level": "info",
    }
    if args.tls_keyfile and args.tls_certfile:
        ssl_kwargs["ssl_keyfile"] = str(args.tls_keyfile)
        ssl_kwargs["ssl_certfile"] = str(args.tls_certfile)

    uvicorn.run(
        "server:create_app",
        host=args.host,
        port=args.port,
        **ssl_kwargs,
    )


if __name__ == "__main__":
    main()
