#!/usr/bin/env python3
"""BioNodulo v2 entry point."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="BioNodulo - Visual bioinformatics pipelines")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    parser.add_argument("--project-root", type=Path, default=None, help="Project/workspace root directory")
    parser.add_argument("--config", type=Path, default=None, help="Path to config YAML file")
    parser.add_argument("--dev", action="store_true", help="Enable development mode with auto-reload")
    parser.add_argument("--mock-tools", action="store_true", help="Mock external tool execution (safe mode)")
    parser.add_argument("--no-mock-tools", action="store_false", dest="mock_tools", help="Execute real tools")
    parser.add_argument("--frontend-dev", action="store_true", help="Proxy frontend from vite dev server")
    parser.add_argument("--tls-keyfile", type=Path, default=None, help="Path to TLS key file for HTTPS")
    parser.add_argument("--tls-certfile", type=Path, default=None, help="Path to TLS certificate file for HTTPS")
    parser.add_argument("--cors-origins", type=str, default="*", help="CORS allowed origins (comma-separated, default: *)")
    parser.add_argument("--multi-user", action="store_true", help="Enable per-user storage isolation")
    parser.set_defaults(mock_tools=None)
    args = parser.parse_args()

    project_dir = Path(__file__).resolve().parent
    if args.project_root:
        os.environ["BIONODULO_ROOT"] = str(args.project_root.resolve())
    else:
        # Default to workspace/ inside the project directory
        default_root = (project_dir / "workspace").resolve()
        os.environ["BIONODULO_ROOT"] = str(default_root)
    if args.config:
        os.environ["BIONODULO_CONFIG"] = str(args.config.resolve())
    if args.mock_tools is not None:
        os.environ["BIONODULO_MOCK_TOOLS"] = "1" if args.mock_tools else "0"

    # Ensure project root exists
    root = Path(os.environ.get("BIONODULO_ROOT", str(project_dir / "workspace"))).resolve()
    root.mkdir(parents=True, exist_ok=True)

    print(f"""
    =========================================
     BioNodulo v2
     Visual bioinformatics pipelines
    =========================================
     Host:    {args.host}:{args.port}
     Root:    {root}
     Mode:    {'mock (safe)' if args.mock_tools else 'real tools'}
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
