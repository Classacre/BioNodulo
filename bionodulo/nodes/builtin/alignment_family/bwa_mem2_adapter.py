"""BWA-MEM2 2.3 metadata and native index-bundle validation."""

from __future__ import annotations

import os
from pathlib import Path

from bionodulo.nodes.command_node import CommandNode


BWA_MEM2_SUFFIXES = (".0123", ".amb", ".ann", ".bwt.2bit.64", ".pac")
BWA_MEM2_PREFIX = "reference"


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
    PACKAGE_CONSTRAINTS = ("bwa-mem2==2.3",)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    VERSION = "2.3"
    GIT_URL = "https://github.com/bwa-mem2/bwa-mem2.git"
    GIT_COMMIT = "7aa5ff6c3330490e5629ab9b7327683d2dce02d6"
    DOCUMENTATION_URL = "https://github.com/bwa-mem2/bwa-mem2/tree/v2.3"
    CITATION_DOIS = ["10.1109/IPDPS49936.2021.00045"]
    CITATION_URLS = ["https://doi.org/10.1109/IPDPS49936.2021.00045"]
    SHELL = False
