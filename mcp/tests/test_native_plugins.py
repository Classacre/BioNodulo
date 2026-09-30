"""Package contracts that prevent shipping a broken or cloud-auth desktop bundle."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from zipfile import ZipFile


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_native_plugins.py"
SPEC = importlib.util.spec_from_file_location("build_native_plugins", SCRIPT)
assert SPEC and SPEC.loader
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


def test_native_plugin_manifest_contracts() -> None:
    assert build.check() == ("0.1.1", "0.1.0")


def test_desktop_bundle_contains_only_local_configuration(tmp_path: Path) -> None:
    target = tmp_path / "desktop.mcpb"
    build.write_zip(target, build.desktop_files())
    with ZipFile(target) as archive:
        names = set(archive.namelist())
        assert {"manifest.json", "server.py", "LICENSE", "pyproject.toml", "uv.lock", "src/bionodulo_mcp/server.py"} <= names
        assert not any(".venv" in name or "__pycache__" in name for name in names)
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["server"]["type"] == "uv"
        assert manifest["server"]["mcp_config"]["env"]["BIONODULO_CLOUD"] == "0"
        assert b'os.environ["BIONODULO_CLOUD"] = "0"' in archive.read("server.py")


def test_archives_are_reproducible(tmp_path: Path) -> None:
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    entries = build.package_files()
    build.write_zip(first, entries)
    build.write_zip(second, entries)
    assert first.read_bytes() == second.read_bytes()


def test_release_archive_never_replaces_different_content(tmp_path: Path) -> None:
    target = tmp_path / "released.zip"
    build.write_release_archive(target, [("entry.txt", b"original")])
    original = target.read_bytes()
    build.write_release_archive(target, [("entry.txt", b"original")])
    assert target.read_bytes() == original
    try:
        build.write_release_archive(target, [("entry.txt", b"changed")])
    except FileExistsError:
        pass
    else:
        raise AssertionError("a published archive was overwritten")
    assert target.read_bytes() == original
