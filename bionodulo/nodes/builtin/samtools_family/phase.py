"""Focused Samtools 1.23.1 owner: Call and phase heterozygous SNPs from a BAM file."""

from __future__ import annotations

from typing import Any

from .adapter import (
    SamtoolsCommandNode,
    GALAXY_ALIAS,
    SAMTOOLS_GALAXY_CITATION_DOIS,
    SAMTOOLS_GALAXY_CITATION_TEXT,
    SAMTOOLS_GALAXY_CITATION_URLS,
    TOOLS_IUC_GIT_COMMIT,
)


class SamtoolsPhaseNode(SamtoolsCommandNode):
    """Call and phase heterozygous SNPs from a BAM file."""

    NODE_ID = "samtools_phase"
    DISPLAY_NAME = "Samtools Phase"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Call and phase heterozygous SNPs, producing phase-set logs and phased BAM outputs."
    SEARCH_ALIASES = [GALAXY_ALIAS, "samtools", "phase", "heterozygous SNPs", "phasing"]
    RETURN_TYPES = ("STATS_FILE", "BAM", "BAM", "BAM")
    RETURN_NAMES = ("phase_sets", "phase0", "phase1", "chimera")
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-phase.html"
    CITATION_DOIS = SAMTOOLS_GALAXY_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_GALAXY_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_GALAXY_CITATION_TEXT
    VERSION = "1.23.1"
    OUTPUT_FILENAMES = (
        "phase_sets.txt",
        "phase_wrapper.0.bam",
        "phase_wrapper.1.bam",
        "phase_wrapper.chimera.bam",
    )
    STDOUT_OUTPUT_INDEX = 0
    UPSTREAM_MANPAGE = "doc/samtools-phase.1"
    UPSTREAM_SOURCE = "phase.c"
    WRAPPER_SOURCE = "tool_collections/samtools/samtools_phase/samtools_phase.xml"
    WRAPPER_GIT_COMMIT = TOOLS_IUC_GIT_COMMIT

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = cls.output_dir(inputs)
        cmd = [
            "samtools",
            "phase",
            "-b",
            str(output / "phase_wrapper"),
        ]
        if inputs.get("ignore_chimeras"):
            cmd.append("-F")
        cmd.extend(
            [
                "-k",
                str(inputs.get("block_length", 13)),
                "-q",
                str(inputs.get("min_het", 37)),
                "-Q",
                str(inputs.get("min_bq", 13)),
                "-D",
                str(inputs.get("read_depth", 256)),
            ]
        )
        if inputs.get("drop_ambiguous"):
            cmd.append("-A")
        if inputs.get("no_pg"):
            cmd.append("--no-PG")
        cmd.append(str(inputs.get("input_bam", inputs.get("bam", ""))))
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bam": ("BAM", {"description": "BAM file to phase"}),
            },
            "optional": {
                "block_length": ("INT", {"default": 13, "min": 1, "description": "Maximum length for local phasing"}),
                "min_het": ("INT", {"default": 37, "min": 0, "description": "Minimum heterozygote score"}),
                "min_bq": ("INT", {"default": 13, "min": 0, "description": "Minimum base quality"}),
                "read_depth": ("INT", {"default": 256, "min": 0, "description": "Maximum read depth"}),
                "ignore_chimeras": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not attempt to fix chimeric reads"},
                ),
                "drop_ambiguous": ("BOOLEAN", {"default": False, "description": "Drop reads with ambiguous phase"}),
                "no_pg": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not add @PG records to phased BAM headers"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
