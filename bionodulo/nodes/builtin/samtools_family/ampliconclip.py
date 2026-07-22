"""Focused Samtools 1.23.1 owner: Clip primer regions from amplicon-aligned BAM files."""

from __future__ import annotations

from typing import Any

from .adapter import (
    SamtoolsCommandNode,
    GALAXY_ALIAS,
    SAMTOOLS_GALAXY_CITATION_DOIS,
    SAMTOOLS_GALAXY_CITATION_TEXT,
    SAMTOOLS_GALAXY_CITATION_URLS,
    _add_if_value,
    _additional_threads,
    _sort_memory,
    TOOLS_IUC_GIT_COMMIT,
)


class SamtoolsAmpliconclipNode(SamtoolsCommandNode):
    """Clip primer regions from amplicon-aligned BAM files."""

    NODE_ID = "samtools_ampliconclip"
    DISPLAY_NAME = "Samtools Ampliconclip"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Clip primer bases from amplicon BAM files and re-sort alignments for downstream analysis."
    SEARCH_ALIASES = [GALAXY_ALIAS, "samtools", "ampliconclip", "primer trimming", "amplicon", "soft clip"]
    RETURN_TYPES = ("BAM", "BEDGRAPH")
    RETURN_NAMES = ("clipped_bam", "primer_counts")
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-ampliconclip.html"
    CITATION_DOIS = SAMTOOLS_GALAXY_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_GALAXY_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_GALAXY_CITATION_TEXT
    VERSION = "1.23.1"
    SHELL = True
    OUTPUT_FILENAMES = ("clipped.bam", "primer_counts.bedgraph")
    UPSTREAM_MANPAGE = "doc/samtools-ampliconclip.1"
    UPSTREAM_SOURCE = "bam_ampliconclip.c"
    UPSTREAM_COLLATE_SOURCE = "bamshuf.c"
    UPSTREAM_FIXMATE_SOURCE = "bam_mate.c"
    UPSTREAM_SORT_SOURCE = "bam_sort.c"
    WRAPPER_SOURCE = "tool_collections/samtools/samtools_ampliconclip/samtools_ampliconclip.xml"
    WRAPPER_GIT_COMMIT = TOOLS_IUC_GIT_COMMIT

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = cls.output_dir(inputs)
        addthreads = str(_additional_threads(inputs))
        primer_counts = output / cls.OUTPUT_FILENAMES[1]
        cmd = [
            "samtools",
            "ampliconclip",
            "--hard-clip" if inputs.get("hard_clip") else "--soft-clip",
        ]
        if inputs.get("no_pg"):
            cmd.append("--no-PG")
        _add_if_value(cmd, "--fail-len", inputs.get("min_length"))
        cmd.extend(["--tolerance", str(inputs.get("tolerance", 5))])
        if inputs.get("strand") and not inputs.get("both_ends"):
            cmd.append("--strand")
        cmd.extend(["-b", str(inputs.get("input_bed", "")), "-u"])
        if inputs.get("both_ends"):
            cmd.append("--both-ends")
        if inputs.get("no_excluded"):
            cmd.append("--no-excluded")
        cmd.extend(["--primer-counts", str(primer_counts)])
        cmd.extend(
            [
                "-@",
                addthreads,
                str(inputs.get("input_bam", inputs.get("bam", ""))),
                "|",
                "samtools",
                "collate",
                "-@",
                addthreads,
                "-O",
                "-u",
                "-",
                "|",
                "samtools",
                "fixmate",
                "-@",
                addthreads,
                "-u",
                "-",
                "-",
                "|",
                "samtools",
                "sort",
                "-@",
                addthreads,
                "-m",
                _sort_memory(inputs),
                "-T",
                str(output / "tmp"),
                "-o",
                str(output / cls.OUTPUT_FILENAMES[0]),
            ]
        )
        return cmd

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if inputs.get("strand") and inputs.get("both_ends"):
            return "strand cannot be combined with both_ends; samtools ampliconclip ignores --strand in that mode"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bed": ("BED", {"description": "BED file defining primer or amplicon intervals"}),
                "input_bam": ("BAM", {"description": "BAM file to clip"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "hard_clip": (
                    "BOOLEAN",
                    {"default": False, "description": "Hard clip primer bases instead of soft clipping"},
                ),
                "strand": (
                    "BOOLEAN",
                    {"default": False, "description": "Only clip reads matching BED strand annotation"},
                ),
                "both_ends": (
                    "BOOLEAN",
                    {"default": False, "description": "Clip both read ends instead of the 5' end only"},
                ),
                "no_excluded": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not write excluded reads to output", "advanced": True},
                ),
                "no_pg": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not add a @PG line to the clipped BAM", "advanced": True},
                ),
                "min_length": (
                    "INT",
                    {"default": "", "min": 0, "description": "Mark reads QCFAIL at this length or shorter"},
                ),
                "tolerance": ("INT", {"default": 5, "min": 0, "description": "Primer match tolerance in bases"}),
                "memory_mb": (
                    "INT",
                    {"default": 768, "min": 1, "description": "Memory per sort thread in MB", "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
