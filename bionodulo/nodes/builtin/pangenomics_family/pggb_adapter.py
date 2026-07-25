"""Shared PGGB 0.7.4 metadata and input staging."""

from __future__ import annotations

import errno
import os
import shutil
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


_LINK_FALLBACK_ERRNOS = {errno.EXDEV, errno.EPERM, errno.ENOSYS}
for _errno_name in ("ENOTSUP", "EOPNOTSUPP"):
    _errno_value = getattr(errno, _errno_name, None)
    if _errno_value is not None:
        _LINK_FALLBACK_ERRNOS.add(_errno_value)

_FASTA_SUFFIXES = (
    ".fasta.gz",
    ".fna.gz",
    ".fas.gz",
    ".fa.gz",
    ".fasta",
    ".fna",
    ".fas",
    ".fa",
)


def path_value(value: Any) -> str | None:
    """Return one non-empty filesystem path."""
    try:
        path = os.fsdecode(os.fspath(value))
    except TypeError:
        return None
    return path if path.strip() else None


def _staged_suffix(source: Path) -> str:
    lower = source.name.lower()
    return next((suffix for suffix in _FASTA_SUFFIXES if lower.endswith(suffix)), ".fa")


def _stage_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and os.path.samefile(source, target):
        return
    if target.exists() or target.is_symlink():
        target.unlink()
    try:
        os.link(source, target)
    except OSError as exc:
        if exc.errno not in _LINK_FALLBACK_ERRNOS:
            raise
        shutil.copy2(source, target)


class PGGBCommandNode(CommandNode):
    """Pinned PGGB metadata with mandatory FASTA-index preparation."""

    CATEGORY = "pangenomics"
    REQUIRED_EXECUTABLES = ["pggb", "samtools", "bash", "cp"]
    REQUIRED_CONDA_PACKAGES = ["pggb", "samtools", "bash", "coreutils"]
    VERSION = "0.7.4"
    CONDA_PACKAGE_CONSTRAINTS = {
        "pggb": VERSION,
        "samtools": "1.23.1",
        "bash": "*",
        "coreutils": "9.5",
    }
    PACKAGE_CONSTRAINTS = (
        f"pggb=={VERSION}",
        "samtools==1.23.1",
        "bash",
        "coreutils==9.5",
    )
    PACKAGE_CONSTRAINT = "; ".join(PACKAGE_CONSTRAINTS)
    GIT_URL = "https://github.com/pangenome/pggb.git"
    GIT_COMMIT = "e25486b9b219877eca82631a13953129386c8b09"
    DOCUMENTATION_URL = (
        "https://github.com/pangenome/pggb/blob/e25486b9b219877eca82631a13953129386c8b09/docs/rst/quick_start.rst"
    )
    CITATION_DOIS = ["10.1038/s41592-024-02430-3"]
    CITATION_URLS = ["https://doi.org/10.1038/s41592-024-02430-3"]
    CITATION_TEXT = "Garrison et al. Building pangenome graphs. Nature Methods (2024)."
    SHELL = False

    UPSTREAM_TAG: ClassVar[str] = "v0.7.4"
    UPSTREAM_SOURCE: ClassVar[str] = "pggb"
    SOURCE_URLS: ClassVar[tuple[str, ...]] = (
        "https://github.com/pangenome/pggb/blob/e25486b9b219877eca82631a13953129386c8b09/pggb",
        "https://github.com/pangenome/pggb/blob/e25486b9b219877eca82631a13953129386c8b09/README.md",
        "https://github.com/pangenome/pggb/blob/e25486b9b219877eca82631a13953129386c8b09/docs/rst/quick_start.rst",
    )
    BIOCONDA_RECIPE_COMMIT: ClassVar[str] = "d9929a470a5703120551635efbad7d27aed87ebd"
    BIOCONDA_RECIPE_URL: ClassVar[str] = (
        "https://github.com/bioconda/bioconda-recipes/blob/"
        "d9929a470a5703120551635efbad7d27aed87ebd/recipes/pggb/meta.yaml"
    )
    BIOCONDA_SOURCE_ARCHIVE_SHA256: ClassVar[str] = "f443a6354f30307573545d03c7491de299ca50dfcba2a12832fb77e0452e46f4"
    BIOCONDA_ODGI_RUNTIME: ClassVar[str] = "0.9.2"
    FAIDX_VERSION: ClassVar[str] = "1.23.1"
    FAIDX_SOURCE_COMMIT: ClassVar[str] = "6efb9b6da35224cf804921dedecf9fb8f411365d"
    EXIT_SEMANTICS: ClassVar[str] = (
        "Any non-zero indexing, PGGB, or compound-shell status fails the node. The "
        "wrapper also fails when PGGB exits zero without exactly one non-empty final GFA "
        "and one non-empty final ODGI artifact."
    )

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        source_text = path_value(inputs.get("input_fasta"))
        if source_text is None:
            raise ValueError("input_fasta must be a non-empty path-like value")
        source = Path(source_text)
        stage_root = outputs[0].parent / "_inputs"
        if stage_root.exists():
            shutil.rmtree(stage_root)
        staged = stage_root / f"input{_staged_suffix(source)}"
        _stage_file(source, staged)
        inputs["input_fasta"] = str(staged)

    async def run(self, **kwargs: Any) -> tuple[Any, ...] | dict[str, Any]:
        result = await super().run(**kwargs)
        if not isinstance(result, tuple):
            return result
        empty = [Path(str(path)) for path in result if Path(str(path)).stat().st_size == 0]
        if empty:
            names = ", ".join(str(path) for path in empty)
            raise RuntimeError(f"PGGB completed but produced empty output artifact(s): {names}")
        return result
