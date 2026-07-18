"""Small path normalization helpers shared by focused assembly adapters."""

from __future__ import annotations

import os
from typing import Any


def normalize_paths(value: Any, label: str) -> list[str]:
    """Return non-empty path strings from one path or a path collection."""

    if isinstance(value, (str, os.PathLike)):
        values = [value]
    elif isinstance(value, (list, tuple)):
        values = list(value)
    else:
        raise TypeError(f"{label} must be a path or a path collection")

    paths: list[str] = []
    for item in values:
        try:
            path = os.fsdecode(os.fspath(item))
        except TypeError as exc:
            raise TypeError(f"each {label} entry must be path-like") from exc
        if not path.strip():
            raise ValueError(f"{label} entries must be non-empty paths")
        paths.append(path)
    return paths
