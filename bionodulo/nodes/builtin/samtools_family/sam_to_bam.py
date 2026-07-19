"""Focused Samtools 1.23.1 owner: Convert SAM alignments to sorted BAM format."""

from __future__ import annotations

from typing import Any

from bionodulo.nodes.builtin._reference_sidecars import (
    validate_colocated_reference_index,
)

from .adapter import (
    SamtoolsCommandNode,
    GALAXY_ALIAS,
    SAMTOOLS_GALAXY_CITATION_DOIS,
    SAMTOOLS_GALAXY_CITATION_TEXT,
    SAMTOOLS_GALAXY_CITATION_URLS,
    _additional_threads,
    _sort_memory,
)


class SamtoolsSamToBamNode(SamtoolsCommandNode):
    """Convert SAM alignments to sorted BAM format."""

    NODE_ID = "samtools_sam_to_bam"
    DISPLAY_NAME = "Samtools SAM to BAM"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Convert SAM alignments to sorted BAM format using a reference FASTA index."
    SEARCH_ALIASES = [
        GALAXY_ALIAS,
        "samtools",
        "SAM to BAM",
        "sorted BAM",
        "reference index",
        "alignment conversion",
    ]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("bam",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-view.html"
    CITATION_DOIS = SAMTOOLS_GALAXY_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_GALAXY_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_GALAXY_CITATION_TEXT
    VERSION = "1.23.1"
    SHELL = True
    OUTPUT_FILENAMES = ("output.bam",)
    UPSTREAM_MANPAGE = "doc/samtools-view.1"
    UPSTREAM_SOURCE = "sam_view.c"
    UPSTREAM_SORT_MANPAGE = "doc/samtools-sort.1"
    UPSTREAM_SORT_SOURCE = "bam_sort.c"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = cls.output_dir(inputs)
        reference_index = str(inputs.get("reference_index", ""))
        addthreads = str(_additional_threads(inputs))
        return [
            "samtools",
            "view",
            "-b",
            "-@",
            addthreads,
            "-t",
            reference_index,
            str(inputs.get("input", "")),
            "|",
            "samtools",
            "sort",
            "-O",
            "bam",
            "-@",
            addthreads,
            "-m",
            _sort_memory(inputs),
            "-o",
            str(output / cls.OUTPUT_FILENAMES[0]),
            "-T",
            str(output / "tmp"),
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return validate_colocated_reference_index(inputs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("SAM", {"description": "SAM alignment file to convert"}),
                "reference": ("FASTA", {"description": "Reference FASTA for resolving SAM target names"}),
                "reference_index": (
                    "FASTA_INDEX",
                    {"description": "Exact colocated <reference>.fai index passed to samtools view -t"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "memory_mb": (
                    "INT",
                    {"default": 768, "min": 1, "description": "Memory per sort thread in MB", "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
