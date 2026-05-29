"""Workspace path helpers shared by CLI, server, and collaboration modules."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def project_root() -> Path:
    """Return the repository/application root directory."""
    return Path(__file__).resolve().parent.parent.parent


def default_workspace_root(base_dir: Path | None = None) -> Path:
    """Return the default BioNodulo workspace, avoiding spaces in tool paths."""
    base = base_dir or project_root()
    workspace = (base / "workspace").resolve()
    if " " in str(workspace):
        workspace = (Path.home() / ".bionodulo" / "workspace").resolve()
    return workspace


def resolve_workspace_root() -> Path:
    """Resolve the configured workspace root from ``BIONODULO_ROOT``."""
    root = os.environ.get("BIONODULO_ROOT", "")
    if root:
        return Path(root).resolve()
    return default_workspace_root()


def ensure_workspace_root(project_dir: Path | None = None) -> Path:
    """Ensure ``BIONODULO_ROOT`` is set and the workspace directory exists."""
    if "BIONODULO_ROOT" not in os.environ:
        os.environ["BIONODULO_ROOT"] = str(default_workspace_root(project_dir))
    root = resolve_workspace_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def ensure_examples_link(workspace_root: Path, project_dir: Path | None = None) -> None:
    """Expose repository examples inside the workspace for template paths."""
    source = (project_dir or project_root()) / "examples"
    target = workspace_root / "examples"
    if not source.exists() or target.exists():
        return
    workspace_root.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(str(source), str(target))
    except OSError:
        shutil.copytree(source, target, dirs_exist_ok=True)
