"""Shared runtime contract for the HTSlib ``bgzip``/``tabix`` nodes.

``bgzip`` and ``tabix`` ship together from HTSlib and are distributed as the
single bioconda ``tabix`` package; the pinned container image provides both
executables. This module holds the metadata common to the four operations,
plus the input staging and validation rules they share.

Staging rationale: both tools discover or write files *by filename sibling*.
``bgzip`` writes ``<input>.gz`` and ``tabix`` writes ``<input>.tbi`` next to
whatever path they are handed, and ``bgzip`` removes its input after a
successful run. Staging the input into the node output directory first (a
hard link where possible, a copy across filesystems) keeps those colocated
artifacts inside the node's own directory instead of next to the user's
original file.
"""

from __future__ import annotations

import errno
import os
import re
import shutil
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


HTSLIB_VERSION = "0.2.5"
HTSLIB_GIT_URL = "https://github.com/samtools/htslib.git"
TABIX_CONTAINER_IMAGE = "quay.io/biocontainers/tabix:0.2.5--ha92aebf_2"

TABIX_CITATION_DOI = "10.1093/bioinformatics/btq671"
TABIX_CITATION_URL = f"https://doi.org/{TABIX_CITATION_DOI}"
TABIX_CITATION_TEXT = (
    "Tabix: fast retrieval of sequence features from generic TAB-delimited files."
)
TABIX_CITATION_EVIDENCE = {
    "identifier": TABIX_CITATION_DOI,
    "source_url": "https://academic.oup.com/bioinformatics/article/27/5/718/262743",
    "checked_at": "2026-09-25",
    "note": (
        "Crossref resolves this DOI to the 2011 Bioinformatics paper describing "
        "tabix and the bgzip block compressor it depends on. This is the software "
        "paper for the tool, not a version-specific runtime DOI."
    ),
}

# EDAM terms are those recorded by the pinned bio.tools 'tabix' snapshot
# (reports/biotools_registry/current/registry.jsonl). The labels were resolved
# against the EDAM release pinned in
# reports/biotools_registry/ontology-and-snapshot-pins.json. The record's
# 'Sorting' operation is deliberately omitted: none of these four nodes sorts,
# and claiming it would overstate what they do.
HTSLIB_TABIX_TOPICS = [
    {"uri": "http://edamontology.org/topic_0622", "label": "Genomics"},
]
HTSLIB_TABIX_OPERATIONS = [
    {"uri": "http://edamontology.org/operation_2409", "label": "Data handling"},
    {"uri": "http://edamontology.org/operation_2422", "label": "Data retrieval"},
]

_PATH_TYPES = frozenset(
    {"FILE", "VCF", "VCF_GZ", "BCF", "BED", "GFF", "GTF", "GFF_GTF", "TSV", "CSV", "TBI"}
)
COMPRESSED_SUFFIXES = (".gz", ".bgz", ".bgzf")

_LINK_FALLBACK_ERRNOS = {errno.EXDEV, errno.EPERM, errno.ENOSYS}
for _errno_name in ("ENOTSUP", "EOPNOTSUPP"):
    _errno_value = getattr(errno, _errno_name, None)
    if _errno_value is not None:
        _LINK_FALLBACK_ERRNOS.add(_errno_value)

_REGION_RE = re.compile(r"^[^:\s]+(?::[0-9]+(?:-[0-9]*)?|:-[0-9]+)?$")


def _as_text(value: Any) -> str | None:
    try:
        return os.fsdecode(os.fspath(value))
    except TypeError:
        return None


def _looks_compressed(path: str) -> bool:
    return path.lower().endswith(COMPRESSED_SUFFIXES)


def stage_input(source_value: Any, target: Path) -> Path:
    """Place one input artifact beside the planned output that will consume it.

    Prefers a hard link; falls back to a copy when the destination filesystem
    cannot link. The link is assembled under a temporary name and atomically
    installed so a failed copy cannot leave a truncated file at the name the
    tool will discover.
    """
    source = Path(os.fsdecode(os.fspath(source_value)))
    target.parent.mkdir(parents=True, exist_ok=True)

    source_lexical = os.path.abspath(os.path.normpath(os.fspath(source)))
    target_lexical = os.path.abspath(os.path.normpath(os.fspath(target)))
    if source_lexical == target_lexical:
        return target
    if target.exists() and not target.is_symlink():
        try:
            if os.path.samefile(source, target):
                return target
        except OSError:
            pass

    if target.exists() or target.is_symlink():
        target.unlink()
    try:
        os.link(source, target)
    except OSError as exc:
        if exc.errno not in _LINK_FALLBACK_ERRNOS:
            raise
        shutil.copy2(source, target)
    return target


class HtslibTabixBase(CommandNode):
    """Metadata, staging, and fail-closed validation for bgzip/tabix nodes."""

    CATEGORY = "genomics"
    REQUIRED_EXECUTABLES = ["bgzip", "tabix"]
    REQUIRED_CONDA_PACKAGES = ["tabix"]
    CONDA_PACKAGE_CONSTRAINTS = {"tabix": f"=={HTSLIB_VERSION}"}
    VERSION = HTSLIB_VERSION
    GIT_URL = HTSLIB_GIT_URL
    RUNTIME_VERSION = HTSLIB_VERSION
    RUNTIME_GIT_URL = HTSLIB_GIT_URL
    CITATION_DOIS = [TABIX_CITATION_DOI]
    CITATION_URLS = [TABIX_CITATION_URL]
    CITATION_TEXT = TABIX_CITATION_TEXT
    KNOWLEDGE = {
        "schema_version": 1,
        "tool_id": "https://bio.tools/tabix",
        "topics": HTSLIB_TABIX_TOPICS,
        "operations": HTSLIB_TABIX_OPERATIONS,
        "citation_evidence": [TABIX_CITATION_EVIDENCE],
        "reviewed_at": "2026-09-25",
    }
    SHELL = False

    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()
    UPSTREAM_MANPAGE: ClassVar[str] = ""
    UPSTREAM_SOURCE: ClassVar[str] = ""

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        """Plan outputs by declared filename.

        The generic extension mapping would name a ``FILE`` return
        ``compressed.out``, but bgzip/tabix write ``<name>.gz``/``<name>.tbi``;
        ``OUTPUT_FILENAMES`` must be authoritative so the run's output-honesty
        check looks for the file the command actually writes.
        """
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / filename for filename in cls.OUTPUT_FILENAMES]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_types = cls.INPUT_TYPES()
        normalized_inputs = dict(inputs)
        for name in input_types.get("optional", {}):
            if normalized_inputs.get(name) == "":
                normalized_inputs.pop(name)
        base_validation = super().VALIDATE_INPUTS(normalized_inputs)
        if base_validation is not True:
            return base_validation

        for category in ("required", "optional"):
            for name, spec in input_types.get(category, {}).items():
                declared_type = spec[0] if isinstance(spec, (list, tuple)) else spec
                declared_types = (
                    (declared_type,) if isinstance(declared_type, str) else tuple(declared_type)
                )
                metadata = spec[1] if isinstance(spec, tuple) and len(spec) > 1 else {}
                value = inputs.get(name)

                if set(declared_types).intersection(_PATH_TYPES):
                    if value is None or (isinstance(value, str) and not value.strip()):
                        if category == "required":
                            return f"Input '{name}' must be a non-empty path"
                        continue
                    text = _as_text(value)
                    if text is None:
                        return f"Input '{name}' must be a path-like value"
                    if not text.strip():
                        return f"Input '{name}' must be a non-empty path"
                    continue

                options = metadata.get("options") if isinstance(metadata, dict) else None
                if options and declared_type == "STRING" and value not in (None, "") and value not in options:
                    return f"{name} must be one of: {', '.join(map(str, options))}"

        return True
