from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_REGISTRY = [
    {
        "id": "bionodulo-examples",
        "name": "BioNodulo example custom nodes",
        "description": "Local example package pattern for teaching custom nodes.",
        "url": "https://github.com/example/bionodulo-custom-nodes",
        "status": "example",
    }
]


def registry_entries(registries: list[str]) -> list[dict[str, Any]]:
    entries = list(DEFAULT_REGISTRY)
    for registry in registries:
        path = Path(registry).expanduser()
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    entries.extend(loaded)
            except json.JSONDecodeError:
                entries.append({"id": path.stem, "name": path.name, "description": "Registry file could not be parsed.", "url": str(path), "status": "invalid"})
        else:
            entries.append({"id": registry, "name": registry, "description": "Remote registry configured; fetch is not automatic in MVP.", "url": registry, "status": "remote"})
    return entries


def install_git(url: str, custom_nodes_dir: Path, *, name: str | None = None) -> dict[str, Any]:
    package_name = _package_name(url, name)
    target = custom_nodes_dir / package_name
    if target.exists():
        return {"ok": False, "status": "exists", "package": package_name, "path": str(target)}
    if shutil.which("git") is None:
        return {"ok": False, "status": "blocked", "message": "git executable was not found on PATH."}
    result = subprocess.run(["git", "clone", "--depth", "1", url, str(target)], capture_output=True, text=True, timeout=120)
    return {"ok": result.returncode == 0, "status": "completed" if result.returncode == 0 else "failed", "package": package_name, "path": str(target), "stdout": result.stdout[-4000:], "stderr": result.stderr[-4000:]}


def update_package(package: str, custom_nodes_dir: Path) -> dict[str, Any]:
    target = _package_path(package, custom_nodes_dir)
    if not (target / ".git").exists():
        return {"ok": False, "status": "blocked", "message": "Package is not a Git checkout.", "package": package}
    result = subprocess.run(["git", "-C", str(target), "pull", "--ff-only"], capture_output=True, text=True, timeout=120)
    return {"ok": result.returncode == 0, "status": "completed" if result.returncode == 0 else "failed", "package": package, "stdout": result.stdout[-4000:], "stderr": result.stderr[-4000:]}


def remove_package(package: str, custom_nodes_dir: Path) -> dict[str, Any]:
    target = _package_path(package, custom_nodes_dir)
    if not target.exists():
        return {"ok": False, "status": "missing", "package": package}
    if target.parent.resolve() != custom_nodes_dir.resolve():
        return {"ok": False, "status": "blocked", "package": package}
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    return {"ok": True, "status": "removed", "package": package}


def _package_name(url: str, name: str | None) -> str:
    raw = name or url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in raw)
    return cleaned or "custom-node-package"


def _package_path(package: str, custom_nodes_dir: Path) -> Path:
    target = (custom_nodes_dir / package).resolve()
    if custom_nodes_dir.resolve() not in (target, *target.parents):
        raise ValueError("Package path is outside custom_nodes_dir.")
    return target
