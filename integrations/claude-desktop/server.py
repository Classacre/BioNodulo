"""Launch the existing BioNodulo MCP implementation in desktop-only mode."""

import os

os.environ["BIONODULO_CLOUD"] = "0"
os.environ["BIONODULO_DESKTOP"] = "1"
os.environ["BIONODULO_DESKTOP_URL"] = "http://127.0.0.1:8765"

from bionodulo_mcp.server import main  # noqa: E402


if __name__ == "__main__":
    main()
