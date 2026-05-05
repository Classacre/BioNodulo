from __future__ import annotations

from pathlib import Path


def safe_node_dir_name(node_id: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in node_id)


def ensure_within(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    root_resolved = root.resolve()
    if root_resolved not in (resolved, *resolved.parents):
        raise ValueError(f"Path {resolved} is outside allowed root {root_resolved}")
    return resolved
