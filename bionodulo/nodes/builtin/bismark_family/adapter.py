"""Shared Bismark 3.1.0 metadata and prepared-genome helpers."""

from __future__ import annotations

import errno
import os
import shutil
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


FASTA_SUFFIX_TIERS = (".fa", ".fa.gz", ".fasta", ".fasta.gz")
BOWTIE2_INDEX_PARTS = ("1", "2", "3", "4", "rev.1", "rev.2")
PREPARED_GENOME_DIRECTORY = "genome"

# The Bismark Rust port is pinned independently from the Bowtie2 executable it
# launches.  Keeping the secondary tool constraint here prevents an align node
# from silently inheriting an environment that contains Bismark but no Bowtie2
# binary (the cloud failure mode this family audit is meant to catch).
BISMARK_VERSION = "3.1.0"
BISMARK_GIT_URL = "https://github.com/FelixKrueger/Bismark.git"
BISMARK_GIT_COMMIT = "e552b8f307a7041bcebed8f8e5a764ebcf7b046c"
BISMARK_SOURCE_ROOT = f"https://github.com/FelixKrueger/Bismark/blob/{BISMARK_GIT_COMMIT}"
BISMARK_PACKAGE_CONSTRAINT = f"bismark=={BISMARK_VERSION}"
BOWTIE2_VERSION = "2.5.5"
BOWTIE2_PACKAGE_CONSTRAINT = f"bowtie2=={BOWTIE2_VERSION}"


def bismark_source_urls(*paths: str) -> tuple[str, ...]:
    """Return immutable source URLs at the audited Bismark revision."""
    return tuple(f"{BISMARK_SOURCE_ROOT}/{path}" for path in paths)


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


def discover_fasta_files(genome_folder: str | os.PathLike[str]) -> tuple[Path, ...]:
    """Return Bismark's first non-empty top-level FASTA extension tier."""
    folder = Path(genome_folder)
    if not folder.exists():
        raise FileNotFoundError(f"Bismark genome folder not found: {folder}")
    if not folder.is_dir():
        raise NotADirectoryError(f"Bismark genome input is not a directory: {folder}")

    for suffix in FASTA_SUFFIX_TIERS:
        matches = sorted(
            (path for path in folder.iterdir() if path.is_file() and path.name.endswith(suffix)),
            key=lambda path: (path.name.lower(), path.name),
        )
        if matches:
            return tuple(matches)
    tiers = ", ".join(FASTA_SUFFIX_TIERS)
    raise FileNotFoundError(f"Bismark genome folder {folder} has no top-level FASTA ({tiers})")


def bowtie2_index_files(prefix: Path, *, large: bool = False) -> tuple[Path, ...]:
    """Return the six Bowtie2 small- or large-index siblings for a prefix."""
    extension = "bt2l" if large else "bt2"
    return tuple(Path(f"{prefix}.{part}.{extension}") for part in BOWTIE2_INDEX_PARTS)


def find_complete_bowtie2_index(conversion_dir: Path, stem: str) -> tuple[Path, ...]:
    """Resolve Bismark's complete small index, falling back to a large index."""
    if not conversion_dir.is_dir():
        raise FileNotFoundError(f"Bismark conversion index directory not found: {conversion_dir}")
    prefix = conversion_dir / stem
    for large in (False, True):
        files = bowtie2_index_files(prefix, large=large)
        if all(path.is_file() and path.stat().st_size > 0 for path in files):
            return files
    required = ", ".join(path.name for path in bowtie2_index_files(prefix))
    raise FileNotFoundError(
        f"Bismark conversion index {prefix} is incomplete; expected all of {required} or the corresponding .bt2l files"
    )


def validate_prepared_genome(
    genome_folder: str | os.PathLike[str],
) -> tuple[Path, ...]:
    """Validate raw FASTA plus complete CT and GA Bowtie2 index siblings."""
    folder = Path(genome_folder)
    fastas = discover_fasta_files(folder)
    bisulfite = folder / "Bisulfite_Genome"
    ct = find_complete_bowtie2_index(bisulfite / "CT_conversion", "BS_CT")
    ga = find_complete_bowtie2_index(bisulfite / "GA_conversion", "BS_GA")
    return (*fastas, *ct, *ga)


def _stage_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError as exc:
        if exc.errno not in _LINK_FALLBACK_ERRNOS:
            raise
        shutil.copy2(source, target)


def stage_fasta_tier(source_folder: Path, target_folder: Path) -> tuple[Path, ...]:
    """Create a clean output folder containing only Bismark's selected FASTAs."""
    fastas = discover_fasta_files(source_folder)
    if source_folder.resolve() == target_folder.resolve():
        raise ValueError("Bismark prepared-genome output must differ from its input folder")
    if target_folder.exists() or target_folder.is_symlink():
        if target_folder.is_dir() and not target_folder.is_symlink():
            shutil.rmtree(target_folder)
        else:
            target_folder.unlink()
    target_folder.mkdir(parents=True)
    staged: list[Path] = []
    for source in fastas:
        target = target_folder / source.name
        _stage_file(source, target)
        staged.append(target)
    return tuple(staged)


def extractor_report_names(bam: Any) -> tuple[str, str]:
    """Derive Bismark's guaranteed M-bias and splitting-report basenames."""
    value = path_value(bam) or "aligned_bam.bam"
    filename = Path(value).name

    splitting_stem = filename
    for suffix in (".bam", ".sam", ".cram"):
        if splitting_stem.endswith(suffix):
            splitting_stem = splitting_stem[: -len(suffix)]
            break

    mbias_stem = filename
    for suffix in ("gz", "sam", "bam", "cram", "txt"):
        if mbias_stem.endswith(suffix):
            mbias_stem = mbias_stem[: -len(suffix)]

    return (
        f"{mbias_stem}M-bias.txt",
        f"{splitting_stem}_splitting_report.txt",
    )


class BismarkCommandNode(CommandNode):
    """Pinned metadata shared by the supported Bismark Rust operations."""

    CATEGORY = "epigenomics"
    REQUIRED_CONDA_PACKAGES = ["bismark"]
    VERSION = BISMARK_VERSION
    GIT_URL = BISMARK_GIT_URL
    GIT_COMMIT = BISMARK_GIT_COMMIT
    DOCUMENTATION_URL = f"{BISMARK_SOURCE_ROOT}/README.md"
    CITATION_DOIS = ["10.1093/bioinformatics/btr167"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btr167"]
    CITATION_TEXT = "Bismark: a flexible aligner and methylation caller for Bisulfite-Seq applications."
    CONDA_PACKAGE_CONSTRAINTS = {"bismark": BISMARK_VERSION}
    PACKAGE_CONSTRAINTS = (BISMARK_PACKAGE_CONSTRAINT,)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    GIT_TAG = "bismark-rust-v3.1.0"
    SOURCE_REF = f"tag bismark-rust-v3.1.0 at {BISMARK_GIT_COMMIT}"
    SOURCE_REVISION = BISMARK_GIT_COMMIT
    SOURCE_URL = f"https://github.com/FelixKrueger/Bismark/tree/{BISMARK_GIT_COMMIT}"
    AUDIT_STATUS = "contract-checked-no-external-execution"
    EXIT_SEMANTICS = (
        "Bismark returns non-zero for malformed arguments, missing inputs, incomplete genome/index bundles, "
        "or alignment/extraction failures; BioNodulo additionally validates every planned artifact after exit 0."
    )
    SHELL = False

    UPSTREAM_TAG: ClassVar[str] = "bismark-rust-v3.1.0"
    UPSTREAM_SOURCE: ClassVar[str] = ""
