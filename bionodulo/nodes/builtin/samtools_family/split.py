"""Focused Samtools 1.23.1 owner: Split a BAM file into per-read-group BAM files."""

from __future__ import annotations

from pathlib import Path

from typing import Any

from .adapter import (
    SamtoolsCommandNode,
    GALAXY_ALIAS,
    SAMTOOLS_GALAXY_CITATION_DOIS,
    SAMTOOLS_GALAXY_CITATION_TEXT,
    SAMTOOLS_GALAXY_CITATION_URLS,
    _additional_threads,
    TOOLS_IUC_GIT_COMMIT,
)


class SamtoolsSplitNode(SamtoolsCommandNode):
    """Split a BAM file into per-read-group BAM files."""

    NODE_ID = "samtools_split"
    DISPLAY_NAME = "Samtools Split"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Split a BAM file into separate BAM files by read group."
    SEARCH_ALIASES = [GALAXY_ALIAS, "samtools", "split", "read groups", "readgroup", "RG"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("readgroup_bams",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-split.html"
    CITATION_DOIS = SAMTOOLS_GALAXY_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_GALAXY_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_GALAXY_CITATION_TEXT
    VERSION = "1.23.1"
    OUTPUT_FILENAMES = ("readgroup_bams",)
    UPSTREAM_MANPAGE = "doc/samtools-split.1"
    UPSTREAM_SOURCE = "bam_split.c"
    WRAPPER_SOURCE = "tool_collections/samtools/samtools_split/samtools_split.xml"
    WRAPPER_GIT_COMMIT = TOOLS_IUC_GIT_COMMIT

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_dir = cls.output_dir(inputs) / cls.OUTPUT_FILENAMES[0]
        cmd = [
            "samtools",
            "split",
            "-f",
            # The pinned source substitutes %! without sanitizing @RG IDs.
            # Use the numeric header index so untrusted BAM metadata cannot
            # escape the planned output directory through a filename.
            str(output_dir / "Read_Group_%#.bam"),
            "--output-fmt",
            "bam",
        ]
        if inputs.get("header"):
            cmd.extend(["-h", str(inputs["header"])])
        if inputs.get("no_pg"):
            cmd.append("--no-PG")
        cmd.extend(
            [
                "-u",
                str(output_dir / "unaccounted.bam"),
                "-@",
                str(_additional_threads(inputs)),
                str(inputs.get("input_bam", inputs.get("bam", ""))),
            ]
        )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        readgroup_dir = node_out / "readgroup_bams"
        readgroup_dir.mkdir(parents=True, exist_ok=True)
        return [readgroup_dir]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bam": ("BAM", {"description": "BAM file to split by read group"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "header": (
                    ("SAM", "BAM", "CRAM"),
                    {"description": "Header for the unaccounted BAM output", "advanced": True},
                ),
                "no_pg": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not add @PG lines to split BAM headers", "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
