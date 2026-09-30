"""Validate and build deterministic BioNodulo plugin archives.

Run from any directory: python mcp/scripts/build_native_plugins.py
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "integrations" / "bionodulo"
DESKTOP = ROOT / "integrations" / "claude-desktop"
DIST = ROOT / "integrations" / "dist"
MCP = ROOT / "mcp"
REMOTE_URL = "https://bionodulo.com/api/mcp"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".venv"}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check() -> str:
    portable = read_json(PACKAGE / "plugin.json")
    portable_mcp = read_json(PACKAGE / "mcp.json")
    claude = read_json(PACKAGE / ".claude-plugin" / "plugin.json")
    claude_mcp = read_json(PACKAGE / ".mcp.json")
    openai_market = read_json(ROOT / ".agents" / "plugins" / "marketplace.json")
    claude_market = read_json(ROOT / ".claude-plugin" / "marketplace.json")
    desktop = read_json(DESKTOP / "manifest.json")

    assert portable["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    assert portable_mcp["$schema"] == "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
    assert portable["name"] == claude["name"] == "bionodulo"
    version = portable["version"]
    assert VERSION_RE.fullmatch(version), f"invalid plugin version: {version}"
    assert version == claude["version"] == desktop["version"]
    assert portable["license"] == claude["license"] == desktop["license"] == "GPL-3.0-only"
    assert portable_mcp["mcpServers"] == {
        "bionodulo": {"type": "streamable-http", "url": REMOTE_URL}
    }
    assert claude_mcp["mcpServers"] == {
        "bionodulo": {"type": "http", "url": REMOTE_URL}
    }
    assert openai_market["plugins"][0]["name"] == "bionodulo"
    assert openai_market["plugins"][0]["source"]["path"] == "./integrations/bionodulo"
    assert claude_market["plugins"][0]["name"] == "bionodulo"
    assert claude_market["plugins"][0]["source"] == "./integrations/bionodulo"
    assert (PACKAGE / "skills" / "bionodulo-workflows" / "SKILL.md").is_file()

    assert desktop["manifest_version"] == "0.4"
    assert desktop["server"]["type"] == "uv"
    assert desktop["server"]["entry_point"] == "server.py"
    assert desktop["server"]["mcp_config"]["env"]["BIONODULO_CLOUD"] == "0"
    assert desktop["server"]["mcp_config"]["env"]["BIONODULO_DESKTOP_URL"] == "http://127.0.0.1:8765"
    assert (DESKTOP / "server.py").is_file()
    assert (MCP / "src" / "bionodulo_mcp" / "server.py").is_file()
    assert (MCP / "pyproject.toml").is_file()
    assert (MCP / "uv.lock").is_file()
    assert "BIONODULO_CLOUD" in (MCP / "src" / "bionodulo_mcp" / "server.py").read_text(encoding="utf-8"), "desktop-only mode missing"

    sensitive = re.compile(r"(?:sk_live_|sk_test_|CLERK_SECRET_KEY|BIONODULO_AUTH_TOKEN)")
    for file in [PACKAGE / "plugin.json", PACKAGE / "mcp.json", PACKAGE / ".mcp.json", DESKTOP / "manifest.json", DESKTOP / "server.py"]:
        assert not sensitive.search(file.read_text(encoding="utf-8")), f"sensitive credential reference in {file}"
    return version


def add_bytes(archive: ZipFile, path: str, data: bytes) -> None:
    info = ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, data, compresslevel=9)


def package_files() -> list[tuple[str, bytes]]:
    files = []
    for file in PACKAGE.rglob("*"):
        if file.is_file() and not any(part in SKIP_PARTS for part in file.parts):
            files.append((file.relative_to(PACKAGE).as_posix(), file.read_bytes()))
    return sorted(files)


def desktop_files() -> list[tuple[str, bytes]]:
    files = [(file.name, file.read_bytes()) for file in [DESKTOP / "manifest.json", DESKTOP / "server.py", DESKTOP / "LICENSE", MCP / "pyproject.toml", MCP / "uv.lock"]]
    # pyproject.toml declares README.md; avoid shipping the legacy installer guide.
    files.append(("README.md", b"# BioNodulo Desktop MCPB\n\nLocal desktop tools only. Start BioNodulo Desktop before using this extension.\n"))
    for file in (MCP / "src" / "bionodulo_mcp").rglob("*.py"):
        files.append((file.relative_to(MCP).as_posix(), file.read_bytes()))
    return sorted(files)


def write_zip(path: Path, entries: list[tuple[str, bytes]]) -> None:
    with ZipFile(path, "w") as archive:
        for name, data in entries:
            add_bytes(archive, name, data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate sources without creating archives")
    args = parser.parse_args()
    version = check()
    if args.check:
        print(f"Plugin manifests and bundle inputs valid ({version})")
        return
    DIST.mkdir(parents=True, exist_ok=True)
    portable_path = DIST / f"bionodulo-plugin-{version}.zip"
    desktop_path = DIST / f"bionodulo-desktop-{version}.mcpb"
    write_zip(portable_path, package_files())
    write_zip(desktop_path, desktop_files())
    print(portable_path)
    print(desktop_path)


if __name__ == "__main__":
    main()
