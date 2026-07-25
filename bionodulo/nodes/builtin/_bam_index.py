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


def validate_colocated_alignment_index(
    inputs: Mapping[str, Any],
    *,
    bam_key: str = "bam",
    index_key: str = "bam_index",
) -> bool | str:
    """Validate the index names searched by DELLY's pinned htslib.

    The bundled htslib commit first checks a CSI sibling for both alignment
    formats.  For BAM it then checks appended and extension-replaced BAI; for
    CRAM it checks appended and extension-replaced CRAI.  Keeping this
    contract separate from the BAI-only helper avoids widening callers whose
    upstream tools really require BAI.
    """
    bam_path = _lexical_path(inputs.get(bam_key), key=bam_key)
    if isinstance(bam_path, str):
        return bam_path

    suffix = bam_path.suffix.lower()
    if suffix == ".cram":
        index_suffixes = (".csi", ".crai")
    else:
        # DELLY's command path is BAM-oriented, and htslib's BAM loader uses
        # BAI after its common CSI probe.  Leave unknown extensions on this
        # conservative BAM branch so validation remains fail-closed.
        index_suffixes = (".csi", ".bai")

    candidates = {Path(f"{bam_path}{index_suffix}") for index_suffix in index_suffixes}
    if suffix:
        candidates.update(bam_path.with_suffix(index_suffix) for index_suffix in index_suffixes)

    index_path = _lexical_path(inputs.get(index_key), key=index_key)
    rendered = ", ".join(f"'{path}'" for path in sorted(candidates, key=str))
    if isinstance(index_path, str):
        return f"{index_path}; expected one of: {rendered}"
    if index_path not in candidates:
        return (
            f"Input '{index_key}' must be an exact colocated index (BAI/CSI/CRAI) for input "
            f"'{bam_key}'; expected one of: {rendered}"
        )
    return True
