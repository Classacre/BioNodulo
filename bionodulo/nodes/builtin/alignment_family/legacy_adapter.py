"""Shared helpers for the audited legacy alignment node IDs."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable


def path_value(value: Any) -> str | None:
    """Return a non-empty path string for one path-like value."""
    try:
        path = os.fsdecode(os.fspath(value))
    except TypeError:
        return None
    return path if path.strip() else None


def path_list(value: Any, *, mapping_keys: tuple[str, ...] = ()) -> list[str]:
    """Normalize one path, an ordered collection, or a paired mapping."""
    if isinstance(value, dict):
        values = [value.get(key) for key in mapping_keys]
    elif isinstance(value, (str, os.PathLike)):
        values = [value]
    elif isinstance(value, (list, tuple)):
        values = list(value)
    else:
        return []

    paths: list[str] = []
    for item in values:
        path = path_value(item)
        if path is None:
            return []
        paths.append(path)
    return paths


def validate_int(
    value: Any,
    name: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> bool | str:
    if isinstance(value, bool) or not isinstance(value, int):
        return f"{name} must be an integer"
    if minimum is not None and value < minimum:
        return f"{name} must be at least {minimum}"
    if maximum is not None and value > maximum:
        return f"{name} must be at most {maximum}"
    return True


def mapped_result(
    result: Any,
    mapper: Callable[[list[Path]], dict[str, Any]],
) -> Any:
    """Turn CommandNode's positional tuple into an explicit output mapping."""
    if not isinstance(result, tuple):
        return result
    mapped = mapper([Path(path) for path in result])

    def normalize(value: Any) -> Any:
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if isinstance(value, tuple):
            return tuple(normalize(item) for item in value)
        return value

    return {"outputs": {name: normalize(value) for name, value in mapped.items()}}
