"""Shared BWA 0.7.19 metadata and index-bundle helpers."""

from __future__ import annotations

import errno
import os
import shutil
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


BWA_INDEX_SUFFIXES = (".amb", ".ann", ".bwt", ".pac", ".sa")
BWA_INDEX_FASTA = "reference.fa"
BWA_INDEX_DIRECTORY = "index"
BWA_VERSION = "0.7.19"
BWA_GIT_URL = "https://github.com/lh3/bwa.git"
BWA_GIT_COMMIT = "b92993c1161e73167181558856567ef2f367e3f0"
BWA_SOURCE_ROOT = f"https://github.com/lh3/bwa/blob/{BWA_GIT_COMMIT}"
BWA_PACKAGE_CONSTRAINT = f"bwa=={BWA_VERSION}"

_LINK_FALLBACK_ERRNOS = {errno.EXDEV, errno.EPERM, errno.ENOSYS}
for _errno_name in ("ENOTSUP", "EOPNOTSUPP"):
    _errno_value = getattr(errno, _errno_name, None)
    if _errno_value is not None:
        _LINK_FALLBACK_ERRNOS.add(_errno_value)


def path_value(value: Any) -> str | None:
    """Return a non-empty filesystem path, or ``None`` for invalid input."""
    try:
        path = os.fsdecode(os.fspath(value))
    except TypeError:
        return None
    return path if path.strip() else None


def bwa_source_urls(*paths: str) -> tuple[str, ...]:
    """Return immutable source URLs at the audited BWA revision."""
    return tuple(f"{BWA_SOURCE_ROOT}/{path}" for path in paths)


def index_sidecars(prefix: Path) -> tuple[Path, ...]:
    """Return BWA's five required files for an inferred index prefix."""
    return tuple(Path(f"{prefix}{suffix}") for suffix in BWA_INDEX_SUFFIXES)


def staged_reference(prefix: Path) -> Path | None:
    """Return the FASTA hint paired with a normal or ``-6`` BWA prefix."""
    if prefix.is_file():
        return prefix
    if prefix.name.endswith(".64"):
        hint = Path(str(prefix)[: -len(".64")])
        if hint.is_file():
            return hint
    return None


def find_index_prefix(index_dir: str | os.PathLike[str], *, require_reference: bool = True) -> Path:
    """Resolve one complete BWA prefix, optionally requiring its source FASTA."""
    directory = Path(index_dir)
    if not directory.exists():
        raise FileNotFoundError(f"BWA index directory not found: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"BWA index input is not a directory: {directory}")

    candidates: list[Path] = []
    for bwt_path in sorted(directory.glob("*.bwt")):
        prefix = Path(str(bwt_path)[: -len(".bwt")])
        has_reference = staged_reference(prefix) is not None
        if (has_reference or not require_reference) and all(
            sidecar.is_file() and sidecar.stat().st_size > 0 for sidecar in index_sidecars(prefix)
        ):
            candidates.append(prefix)

    if not candidates:
        members = (*(("staged FASTA",) if require_reference else ()), *BWA_INDEX_SUFFIXES)
        required = ", ".join(members)
        layout = "colocated" if require_reference else "sibling"
        raise FileNotFoundError(f"BWA index directory {directory} has no complete {layout} prefix ({required})")
    if len(candidates) != 1:
        names = ", ".join(prefix.name for prefix in candidates)
        raise ValueError(f"BWA index directory {directory} contains multiple complete prefixes: {names}")
    return candidates[0]


def planned_or_index_prefix(
    index_dir: str | os.PathLike[str],
    *,
    require_reference: bool = False,
) -> Path:
    """Resolve a complete BWA bundle or its deterministic dry-run prefix."""
    directory = Path(index_dir)
    try:
        return find_index_prefix(directory, require_reference=require_reference)
    except FileNotFoundError:
        if not directory.exists():
            return directory / BWA_INDEX_FASTA
        if directory.is_dir() and not any(
            item.is_file() and item.name.endswith(BWA_INDEX_SUFFIXES) for item in directory.iterdir()
        ):
            return directory / BWA_INDEX_FASTA
        raise


def validate_read_group(value: Any) -> bool | str:
    """Mirror ``bwa_set_rg`` validation for samse, sampe, and mem."""
    if value in (None, ""):
        return True
    if not isinstance(value, str):
        return "read_group must be a string"
    if not value.startswith("@RG"):
        return "read_group must start with @RG"
    if "\t" in value:
        return "read_group must use escaped \\t separators, not literal tabs"
    marker = "\\tID:"
    if marker not in value:
        return "read_group must contain an ID field separated by escaped \\t"
    identifier = value.split(marker, 1)[1].split("\\t", 1)[0]
    if len(identifier) > 255:
        return "read_group ID must be at most 255 characters"
    return True


def stage_file(source: Path, target: Path) -> None:
    """Hard-link a staged artifact, copying only across unsupported filesystems."""
    target.parent.mkdir(parents=True, exist_ok=True)
    source_lexical = os.path.abspath(os.path.normpath(os.fspath(source)))
    target_lexical = os.path.abspath(os.path.normpath(os.fspath(target)))
    if source_lexical == target_lexical:
        return
    if not target.is_symlink() and target.exists() and os.path.samefile(source, target):
        return
    if target.exists() or target.is_symlink():
        target.unlink()
    try:
        os.link(source, target)
    except OSError as exc:
        if exc.errno not in _LINK_FALLBACK_ERRNOS:
            raise
        shutil.copy2(source, target)


class BwaCommandNode(CommandNode):
    """Pinned metadata shared by the documented BWA operations."""

    CATEGORY = "alignment"
    REQUIRED_EXECUTABLES = ["bwa"]
    REQUIRED_CONDA_PACKAGES = ["bwa"]
    VERSION = BWA_VERSION
    GIT_URL = BWA_GIT_URL
    GIT_COMMIT = BWA_GIT_COMMIT
    DOCUMENTATION_URL = f"{BWA_SOURCE_ROOT}/bwa.1"
    CITATION_DOIS = ["10.1093/bioinformatics/btp324"]
    CITATION_URLS = [
        "https://doi.org/10.1093/bioinformatics/btp324",
        "https://arxiv.org/abs/1303.3997",
    ]
    CITATION_TEXT = (
        "Fast and accurate short read alignment with Burrows-Wheeler transform; "
        "Aligning sequence reads, clone sequences and assembly contigs with BWA-MEM."
    )
    CONDA_PACKAGE_CONSTRAINTS = {"bwa": BWA_VERSION}
    PACKAGE_CONSTRAINTS = (BWA_PACKAGE_CONSTRAINT,)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    GIT_TAG = "v0.7.19"
    SOURCE_REF = f"tag v0.7.19 at {BWA_GIT_COMMIT}"
    SOURCE_REVISION = BWA_GIT_COMMIT
    SOURCE_URL = f"https://github.com/lh3/bwa/tree/{BWA_GIT_COMMIT}"
    AUDIT_STATUS = "contract-checked-no-external-execution"
    EXIT_SEMANTICS = (
        "BWA subcommands return non-zero for malformed arguments, unreadable inputs, "
        "or missing index members; BioNodulo additionally validates planned artifacts "
        "after a zero exit."
    )
    SHELL = False

    UPSTREAM_TAG: ClassVar[str] = "v0.7.19"
    UPSTREAM_MANPAGE: ClassVar[str] = "bwa.1"
    UPSTREAM_SOURCE: ClassVar[str] = ""
