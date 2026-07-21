"""BWA-MEM2 2.3 metadata and native index-bundle validation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


BWA_MEM2_SUFFIXES = (".0123", ".amb", ".ann", ".bwt.2bit.64", ".pac")
BWA_MEM2_PREFIX = "reference"
BWA_MEM2_VERSION = "2.3"
BWA_MEM2_GIT_URL = "https://github.com/bwa-mem2/bwa-mem2.git"
BWA_MEM2_GIT_COMMIT = "7aa5ff6c3330490e5629ab9b7327683d2dce02d6"
BWA_MEM2_SOURCE_ROOT = f"https://github.com/bwa-mem2/bwa-mem2/blob/{BWA_MEM2_GIT_COMMIT}"
BWA_MEM2_PACKAGE_CONSTRAINT = f"bwa-mem2=={BWA_MEM2_VERSION}"


def bwa_mem2_source_urls(*paths: str) -> tuple[str, ...]:
    """Return immutable source URLs at the audited BWA-MEM2 revision."""
    return tuple(f"{BWA_MEM2_SOURCE_ROOT}/{path}" for path in paths)


def validate_read_group(value: Any) -> bool | str:
    """Mirror BWA-MEM2's ``bwa_set_rg`` checks for a complete RG line."""
    if value in (None, ""):
        return True
    if not isinstance(value, str):
        return "read_group must be a string"
    if not value.startswith("@RG"):
        return "read_group must start with @RG"
    normalized = value.replace("\\t", "\t")
    marker = "\tID:"
    if marker not in normalized:
        return "read_group must contain an ID field"
    identifier = normalized.split(marker, 1)[1].split("\t", 1)[0]
    if len(identifier) > 255:
        return "read_group ID must be at most 255 characters"
    return True


def index_members(prefix: Path) -> tuple[Path, ...]:
    return tuple(Path(f"{prefix}{suffix}") for suffix in BWA_MEM2_SUFFIXES)


def find_index_prefix(index_dir: str | os.PathLike[str]) -> Path:
    directory = Path(index_dir)
    if not directory.exists():
        raise FileNotFoundError(f"BWA-MEM2 index directory not found: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"BWA-MEM2 index input is not a directory: {directory}")

    candidates: list[Path] = []
    for lead in sorted(directory.glob(f"*{BWA_MEM2_SUFFIXES[0]}")):
        prefix = Path(str(lead)[: -len(BWA_MEM2_SUFFIXES[0])])
        if all(member.is_file() and member.stat().st_size > 0 for member in index_members(prefix)):
            candidates.append(prefix)
    if not candidates:
        required = ", ".join(BWA_MEM2_SUFFIXES)
        raise FileNotFoundError(f"BWA-MEM2 index directory {directory} has no complete prefix ({required})")
    if len(candidates) != 1:
        names = ", ".join(prefix.name for prefix in candidates)
        raise ValueError(f"BWA-MEM2 index directory {directory} contains multiple complete prefixes: {names}")
    return candidates[0]


def planned_or_index_prefix(index_dir: str | os.PathLike[str]) -> Path:
    directory = Path(index_dir)
    try:
        return find_index_prefix(directory)
    except FileNotFoundError:
        if not directory.exists() or (directory.is_dir() and not any(directory.iterdir())):
            return directory / BWA_MEM2_PREFIX
        raise


class BwaMem2CommandNode(CommandNode):
    CATEGORY = "alignment"
    REQUIRED_EXECUTABLES = ["bwa-mem2"]
    REQUIRED_CONDA_PACKAGES = ["bwa-mem2"]
    PACKAGE_CONSTRAINTS = (BWA_MEM2_PACKAGE_CONSTRAINT,)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    CONDA_PACKAGE_CONSTRAINTS = {"bwa-mem2": BWA_MEM2_VERSION}
    VERSION = BWA_MEM2_VERSION
    GIT_URL = BWA_MEM2_GIT_URL
    GIT_COMMIT = BWA_MEM2_GIT_COMMIT
    DOCUMENTATION_URL = f"{BWA_MEM2_SOURCE_ROOT}/README.md"
    CITATION_DOIS = ["10.1109/IPDPS.2019.00041"]
    CITATION_URLS = ["https://doi.org/10.1109/IPDPS.2019.00041"]
    CITATION_TEXT = "Efficient architecture-aware acceleration of BWA-MEM for multicore systems."
    GIT_TAG = "v2.3"
    SOURCE_REF = f"tag v2.3 at {BWA_MEM2_GIT_COMMIT}"
    SOURCE_REVISION = BWA_MEM2_GIT_COMMIT
    SOURCE_URL = f"https://github.com/bwa-mem2/bwa-mem2/tree/{BWA_MEM2_GIT_COMMIT}"
    AUDIT_STATUS = "contract-checked-no-external-execution"
    EXIT_SEMANTICS = (
        "BWA-MEM2 returns non-zero for malformed arguments, missing reads, or incomplete "
        "native index members; BioNodulo validates every planned index and output artifact "
        "after a zero exit."
    )
    SHELL = False
