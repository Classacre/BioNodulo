"""Pinned Samtools reference preparation with explicit sidecar outputs.

The catalog has no separate stable sequence-dictionary producer ID. Keeping
``faidx`` and ``dict`` in this one reference-preparation contract preserves the
943 stable IDs while making both artifacts visible in the DAG.
"""

from __future__ import annotations

import errno
import os
import shutil
from pathlib import Path
from typing import Any

from .adapter import SamtoolsCommandNode


_LINK_FALLBACK_ERRNOS = {errno.EXDEV, errno.EPERM, errno.ENOSYS}
for _errno_name in ("ENOTSUP", "EOPNOTSUPP"):
    _errno_value = getattr(errno, _errno_name, None)
    if _errno_value is not None:
        _LINK_FALLBACK_ERRNOS.add(_errno_value)


class SamtoolsFaidxNode(SamtoolsCommandNode):
    """Stage a FASTA and create its FAI and sequence dictionary siblings."""

    NODE_ID = "samtools_faidx"
    DISPLAY_NAME = "Samtools Faidx"
    DESCRIPTION = "Stage a reference FASTA and create colocated FAI and sequence dictionary sidecars"
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "samtools",
        "faidx",
        "dict",
        "FASTA index",
        "sequence dictionary",
        "fai",
    ]
    RETURN_TYPES = ("FASTA", "FASTA_INDEX", "SEQUENCE_DICTIONARY")
    RETURN_NAMES = ("reference", "fai_index", "sequence_dictionary")
    OUTPUT_FILENAMES = ("reference.fa", "reference.fa.fai", "reference.dict")
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-faidx.html"
    UPSTREAM_MANPAGE = "doc/samtools-faidx.1"
    UPSTREAM_SOURCE = "faidx.c"
    UPSTREAM_DICT_MANPAGE = "doc/samtools-dict.1"
    UPSTREAM_DICT_SOURCE = "dict.c"
    SHELL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference": (
                    "FASTA",
                    {"description": "Reference FASTA to stage and index"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        reference = str(inputs.get("reference", ""))
        return [
            "samtools",
            "faidx",
            "-@",
            str(inputs.get("threads", 1)),
            "--fai-idx",
            str(output / cls.OUTPUT_FILENAMES[1]),
            reference,
            "&&",
            "samtools",
            "dict",
            "-u",
            "file:reference.fa",
            "-o",
            str(output / cls.OUTPUT_FILENAMES[2]),
            reference,
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        try:
            reference = os.fsdecode(os.fspath(inputs.get("reference")))
        except TypeError:
            return "Input 'reference' must be a non-empty path-like value"
        if not reference.strip():
            return "Input 'reference' must be a non-empty path-like value"
        if reference.lower().endswith((".gz", ".bgz", ".bgzf")):
            return (
                "Input 'reference' must be an uncompressed FASTA; compressed "
                "references require an additional GZI sidecar"
            )
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        source = Path(os.fsdecode(os.fspath(inputs["reference"])))
        staged_reference = outputs[0]
        staged_reference.parent.mkdir(parents=True, exist_ok=True)

        source_lexical = os.path.abspath(os.path.normpath(os.fspath(source)))
        staged_lexical = os.path.abspath(
            os.path.normpath(os.fspath(staged_reference))
        )
        if source_lexical == staged_lexical:
            inputs["reference"] = str(staged_reference)
            return
        if (
            not staged_reference.is_symlink()
            and staged_reference.exists()
            and os.path.samefile(source, staged_reference)
        ):
            inputs["reference"] = str(staged_reference)
            return

        if staged_reference.exists() or staged_reference.is_symlink():
            staged_reference.unlink()
        try:
            os.link(source, staged_reference)
        except OSError as exc:
            if exc.errno not in _LINK_FALLBACK_ERRNOS:
                raise
            shutil.copy2(source, staged_reference)
        inputs["reference"] = str(staged_reference)
