"""Path utilities for BioNodulo.

Provides filesystem-safe name sanitization and security checks
for path containment within root directories.
"""

from __future__ import annotations

import re
from pathlib import Path


def safe_node_dir_name(node_id: str) -> str:
    """Sanitize a node ID for safe use as a filesystem directory name.

    Replaces unsafe characters with underscores and collapses multiple
    underscores into one. Strips leading/trailing underscores.

    Args:
        node_id: The node identifier to sanitize.

    Returns:
        A filesystem-safe directory name.

    Example:
        >>> safe_node_dir_name("FastQC_v0.11.9")
        \'FastQC_v0_11_9\'
    """
    # Replace any non-alphanumeric, non-hyphen, non-underscore with underscore
    safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", node_id)
    # Collapse multiple underscores
    safe = re.sub(r"_+", "_", safe)
    # Strip leading/trailing underscores
    safe = safe.strip("_")
    # Ensure not empty
    if not safe:
        safe = "node"
    return safe


def ensure_within(path: Path, root: Path) -> Path:
    """Ensure a resolved path is within a root directory.

    Resolves both paths absolutely and raises ValueError if the
    target path attempts to escape the root directory (path traversal).

    Args:
        path: The path to validate and resolve.
        root: The root directory that must contain path.

    Returns:
        The resolved absolute path.

    Raises:
        ValueError: If the path is outside the root directory.
    """
    resolved_root = root.resolve()
    # Strip leading slash so absolute-looking paths are treated as relative to root
    path_str = str(path)
    if path_str.startswith('/'):
        path_str = path_str[1:]
    resolved_path = (resolved_root / path_str).resolve()

    # Check path containment
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(
            f"Path \'{path}\' is outside root directory \'{root}\'"
        ) from exc

    return resolved_path


def get_run_dir(runs_dir: Path, run_id: str) -> Path:
    """Return the run-specific directory path, creating it if needed.

    Args:
        runs_dir: Base runs directory from settings.
        run_id: Unique run identifier.

    Returns:
        Resolved path to the run directory.
    """
    run_dir = (runs_dir / run_id).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def get_node_output_dir(run_dir: Path, node_id: str) -> Path:
    """Return the output directory for a specific node within a run.

    Args:
        run_dir: The run directory.
        node_id: Node identifier (will be sanitized).

    Returns:
        Resolved path to the node output directory.
    """
    safe = safe_node_dir_name(node_id)
    node_dir = (run_dir / "nodes" / safe).resolve()
    node_dir.mkdir(parents=True, exist_ok=True)
    return node_dir
