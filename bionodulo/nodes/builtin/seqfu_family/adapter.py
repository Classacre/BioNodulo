"""Shared runtime contract for the SeqFu family nodes.

SeqFu is a suite of FASTX utilities. This module holds the metadata, knowledge
provenance, output planning, and path validation that every SeqFu node inherits;
each operation lives in its own thin owner module next to this file.

The command syntax implemented here was read from the pinned container image
(``quay.io/biocontainers/seqfu:1.28.0--h41da26b_0``), not from memory:
``seqfu stats``, ``seqfu count`` and ``seqfu list`` all write their report or
records to **stdout**, so the owners set ``STDOUT_OUTPUT_INDEX = 0`` and this
base class plans exactly one output file whose name matches.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


BIONODULO_BUILTIN_ALIAS = "BioNodulo builtin"
SEQFU_VERSION = "1.28.0"
SEQFU_GIT_URL = "https://github.com/telatin/seqfu2.git"
# Tag v1.28.0 of telatin/seqfu2, read from the GitHub ref API on 2026-09-25.
SEQFU_GIT_COMMIT = "4a1cb45d32bddee8b7cac19e1d038a281ff1d996"
SEQFU_DOCUMENTATION_URL = "https://telatin.github.io/seqfu2/"
SEQFU_CITATION_DOIS = ["10.3390/bioengineering8050059"]
SEQFU_CITATION_URLS = [f"https://doi.org/{doi}" for doi in SEQFU_CITATION_DOIS]
SEQFU_CITATION_TEXT = (
    "SeqFu: A suite of utilities for the robust and reproducible manipulation of sequence files."
)
SEQFU_CITATION_EVIDENCE = {
    "identifier": SEQFU_CITATION_DOIS[0],
    "source_url": "https://doi.org/10.3390/bioengineering8050059",
    "checked_at": "2026-09-25",
    "note": (
        "The bio.tools 'seqfu' record lists this as the primary publication; it is the "
        "SeqFu software paper (Bioengineering 8(5):59), not a version-specific DOI for "
        "the pinned 1.28.0 runtime."
    ),
}
# EDAM labels are taken verbatim from the seqfu record in the pinned registry
# snapshot (reports/biotools_registry/current/registry.jsonl), which carries the
# annotations exported by bio.tools. The one label also checked in
# reports/biotools_registry/ontology-and-snapshot-pins.json (topic_0080 ->
# "Sequence analysis") agrees. No label here was written from memory.
SEQFU_EDAM_TOPICS = [
    {"uri": "http://edamontology.org/topic_0077", "label": "Nucleic acids"},
    {"uri": "http://edamontology.org/topic_0080", "label": "Sequence analysis"},
]
SEQFU_EDAM_OPERATIONS = [
    {"uri": "http://edamontology.org/operation_2478", "label": "Nucleic acid sequence analysis"},
]


def _path_values(value: Any) -> list[str]:
    """Normalize a path input (single value or list) into non-empty strings."""
    if value is None or value == "":
        return []
    if isinstance(value, (str, os.PathLike)):
        return [os.fsdecode(os.fspath(value))]
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [os.fsdecode(os.fspath(item)) for item in value]
    return []


class SeqfuBase(CommandNode):
    """Metadata, knowledge, output planning, and fail-closed path validation."""

    CATEGORY = "sequence"
    REQUIRED_EXECUTABLES = ["seqfu"]
    REQUIRED_CONDA_PACKAGES = ["seqfu"]
    VERSION = SEQFU_VERSION
    GIT_URL = SEQFU_GIT_URL
    GIT_COMMIT = SEQFU_GIT_COMMIT
    DOCUMENTATION_URL = SEQFU_DOCUMENTATION_URL
    CITATION_DOIS = list(SEQFU_CITATION_DOIS)
    CITATION_URLS = list(SEQFU_CITATION_URLS)
    CITATION_TEXT = SEQFU_CITATION_TEXT
    KNOWLEDGE = {
        "schema_version": 1,
        "tool_id": "https://bio.tools/seqfu",
        "topics": SEQFU_EDAM_TOPICS,
        "operations": SEQFU_EDAM_OPERATIONS,
        "citation_evidence": [SEQFU_CITATION_EVIDENCE],
        "reviewed_at": "2026-09-25",
    }
    SHELL = False

    # Input port types that name a filesystem path and must therefore be
    # non-empty, fail-closed values.
    PATH_INPUT_TYPES: ClassVar[frozenset[str]] = frozenset(
        {"FILE", "DIRECTORY", "FASTA", "FASTQ", "FASTA_LIST", "FASTQ_LIST", "FILE_LIST"}
    )

    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        if cls.RETURN_TYPES == ("DIRECTORY",) and not cls.OUTPUT_FILENAMES:
            return [node_out]
        return [node_out / filename for filename in cls.OUTPUT_FILENAMES]

    @classmethod
    def VERIFY_OUTPUTS(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        if cls.RETURN_TYPES == ("DIRECTORY",):
            if len(outputs) != 1 or not any(path.is_file() for path in outputs[0].rglob("*")):
                raise RuntimeError(f"{cls.NODE_ID} produced no files in its output directory")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_types = cls.INPUT_TYPES()
        normalized = dict(inputs)
        for name in input_types.get("optional", {}):
            if normalized.get(name) == "":
                normalized.pop(name)
        base_validation = super().VALIDATE_INPUTS(normalized)
        if base_validation is not True:
            return base_validation

        for category in ("required", "optional"):
            for name, spec in input_types.get(category, {}).items():
                declared = spec[0] if isinstance(spec, (list, tuple)) and spec else spec
                declared_types = (declared,) if isinstance(declared, str) else tuple(declared)
                if not cls.PATH_INPUT_TYPES.intersection(declared_types):
                    continue
                raw_value = inputs.get(name)
                if raw_value in (None, "", []):
                    if category == "required":
                        return f"Required input '{name}' is missing or empty"
                    continue
                try:
                    values = _path_values(raw_value)
                except TypeError:
                    return f"Input '{name}' must contain only path-like values"
                if not values or any(not value.strip() for value in values):
                    return f"Input '{name}' must contain only non-empty paths"
        return True
