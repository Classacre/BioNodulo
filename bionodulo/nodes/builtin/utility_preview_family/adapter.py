"""Shared helpers and source authority for native utility nodes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode


PYTHON_VERSION = "3.12.13"
PYTHON_GIT_URL = "https://github.com/python/cpython.git"
PYTHON_GIT_COMMIT = "3bb231a6a5dc02b95658877318bf61501a7209e9"
INTERNAL_GIT_URL = "https://github.com/Classacre/BioNodulo.git"
INTERNAL_BASELINE_COMMIT = "f3eef3bc12596f02e843f96fba7cf6d82e9078c5"
INTERNAL_BASELINE_BLOB = "014477af4f1b9b95764506d721e896c540972cc9"


def path_value(value: Any) -> str:
    """Return one non-empty filesystem value."""

    try:
        result = os.fsdecode(os.fspath(value))
    except TypeError:
        return ""
    return result if result.strip() else ""


def validate_int(
    value: Any,
    key: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> bool | str:
    if isinstance(value, bool) or not isinstance(value, int):
        return f"Input '{key}' must be an integer"
    if minimum is not None and value < minimum:
        return f"Input '{key}' must be at least {minimum}"
    if maximum is not None and value > maximum:
        return f"Input '{key}' must be at most {maximum}"
    return True


def validate_regular_file(
    value: Any,
    *,
    key: str = "file",
    extensions: set[str] | frozenset[str] | None = None,
    label: str = "File",
) -> bool | str:
    raw_path = path_value(value)
    if not raw_path:
        return f"Required input '{key}' is missing"
    path = Path(raw_path)
    if extensions is not None and path.suffix.lower() not in extensions:
        allowed = ", ".join(sorted(extensions))
        return f"{label} must use one of these extensions: {allowed}; got {path.suffix or '<none>'}"
    if not path.exists():
        return f"{label} not found: {path}"
    if not path.is_file():
        return f"{label} is not a regular file: {path}"
    return True


def node_output_path(context: Any, node_id: str, filename: str) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context is not None else ".")
    output_dir = base / node_id
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / filename


class PythonUtilityNode(BaseNode):
    """CPython-backed native node with a pinned standard-library authority."""

    CATEGORY = "Utility"
    REQUIRES_EXTERNAL_TOOLS = False
    VERSION = PYTHON_VERSION
    GIT_URL = PYTHON_GIT_URL
    GIT_COMMIT = PYTHON_GIT_COMMIT
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/"
    SOURCE_AUTHORITIES = {
        "CPython": (PYTHON_VERSION, PYTHON_GIT_COMMIT),
        "BioNodulo utility baseline": (INTERNAL_BASELINE_COMMIT, INTERNAL_BASELINE_BLOB),
    }
