"""Focused Samtools 1.23.1 owner: Report alignment counts per reference sequence from a BAM/CRAM index."""

from __future__ import annotations

from typing import Any

from .adapter import (
    SamtoolsCommandNode,
    GALAXY_ALIAS,
    SAMTOOLS_CITATION_DOIS,
    SAMTOOLS_CITATION_TEXT,
    SAMTOOLS_CITATION_URLS,
    _additional_threads,
    validate_index_pairs,
)


class SamtoolsIdxstatsNode(SamtoolsCommandNode):
    """Report alignment counts per reference sequence from a BAM/CRAM index."""

    NODE_ID = "samtools_idxstats"
    DISPLAY_NAME = "Samtools Idxstats"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Report mapped and unmapped read counts per reference sequence from a BAM or CRAM index."
    SEARCH_ALIASES = [GALAXY_ALIAS, "samtools", "idxstats", "index stats", "BAM index", "MultiQC"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("idxstats",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-idxstats.html"
    CITATION_DOIS = SAMTOOLS_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_CITATION_TEXT
    VERSION = "1.23.1"
    OUTPUT_FILENAMES = ("idxstats.tsv",)
    STDOUT_OUTPUT_INDEX = 0
    UPSTREAM_MANPAGE = "doc/samtools-idxstats.1"
    UPSTREAM_SOURCE = "bam_index.c"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return [
            "samtools",
            "idxstats",
            "-@",
            str(_additional_threads(inputs)),
            "-X",
            str(inputs.get("input", inputs.get("bam", ""))),
            str(inputs.get("bam_index", "")),
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        # ``idxstats -X`` passes the index path explicitly to Samtools, so the
        # index need not use a sibling filename.  Keep the data/index pairing
        # explicit without rejecting the custom location that -X is for.
        return validate_index_pairs(
            inputs,
            data_key="input",
            index_key="bam_index",
            required=True,
        )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "Indexed BAM alignment file"}),
                "bam_index": (
                    "BAI",
                    {"description": "Explicit BAI paired with input and passed through idxstats -X"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }
