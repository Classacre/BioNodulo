from __future__ import annotations

import argparse
import threading
import time
import webbrowser

import uvicorn


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the BioNodulo local web app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--mock-tools", action="store_true", help="Default new runs to mock tool execution.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.mock_tools:
        import os

        os.environ["BIONODULO_MOCK_TOOLS"] = "1"

    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        threading.Thread(target=lambda: (time.sleep(1.0), webbrowser.open(url)), daemon=True).start()

    uvicorn.run("server:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
