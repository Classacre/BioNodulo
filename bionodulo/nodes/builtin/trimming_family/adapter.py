"""Shared validation and output-path helpers for focused trimming nodes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def read_paths(value: Any, *, key: str = "reads") -> list[str]:
    if isinstance(value, (str, os.PathLike)):
        values = [value]
    elif isinstance(value, (list, tuple)):
        values = list(value)
    else:
        raise TypeError(f"{key} must be a path or an ordered path collection")

    paths: list[str] = []
    for item in values:
        try:
            path = os.fsdecode(os.fspath(item))
        except TypeError as exc:
            raise TypeError(f"each {key} entry must be path-like") from exc
        if not path.strip():
            raise ValueError(f"{key} paths must be non-empty")
        paths.append(path)
    return paths


def output_dir(output_dir: str | Path, node_id: str) -> Path:
    path = Path(output_dir) / node_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_int(
    value: Any,
    key: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> bool | str:
    if isinstance(value, bool) or not isinstance(value, int):
        return f"{key} must be an integer."
    if minimum is not None and value < minimum:
        return f"{key} must be at least {minimum}."
    if maximum is not None and value > maximum:
        return f"{key} must be at most {maximum}."
    return True
