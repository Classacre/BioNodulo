"""Shared validation for CLI tools that discover a BAM's sibling BAI."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def _lexical_path(value: Any, *, key: str) -> Path | str:
    try:
        raw_path = os.fspath(value)
    except TypeError:
        return f"Input '{key}' must be a non-empty path-like value"
    decoded_path = os.fsdecode(raw_path)
    if not decoded_path.strip():
        return f"Input '{key}' must be a non-empty path-like value"
    return Path(os.path.abspath(os.path.normpath(decoded_path)))


def validate_colocated_bam_index(
    inputs: Mapping[str, Any],
    *,
    bam_key: str = "bam",
    index_key: str = "bam_index",
) -> bool | str:
    """Require an exact ``<bam>.bai`` path without touching the filesystem."""
    bam_path = _lexical_path(inputs.get(bam_key), key=bam_key)
    if isinstance(bam_path, str):
        return bam_path

    expected_index = Path(f"{bam_path}.bai")
    index_path = _lexical_path(inputs.get(index_key), key=index_key)
    if isinstance(index_path, str):
        return f"{index_path}; expected '{expected_index}' for input '{bam_key}'"
    if index_path != expected_index:
        return (
            f"Input '{index_key}' must be the exact colocated index for input "
            f"'{bam_key}'; expected '{expected_index}'"
        )
    return True
