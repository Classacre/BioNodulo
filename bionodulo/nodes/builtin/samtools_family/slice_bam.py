"""Focused Samtools 1.23.1 owner: Restrict a BAM file to BED, contig, or manual regions and sort the result."""

from __future__ import annotations

from typing import Any

from bionodulo.nodes.builtin._bam_index import validate_colocated_bam_index

from .adapter import (
    SamtoolsCommandNode,
    GALAXY_ALIAS,
    SAMTOOLS_GALAXY_CITATION_DOIS,
    SAMTOOLS_GALAXY_CITATION_TEXT,
    SAMTOOLS_GALAXY_CITATION_URLS,
    _additional_threads,
    _as_csv_list,
    _sort_memory,
    TOOLS_IUC_GIT_COMMIT,
)


class SamtoolsSliceBamNode(SamtoolsCommandNode):
    """Restrict a BAM file to BED, contig, or manual regions and sort the result."""

    NODE_ID = "samtools_slice_bam"
    DISPLAY_NAME = "Samtools Slice BAM"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Slice an indexed BAM to BED intervals, contigs, or manually supplied genomic regions."
    SEARCH_ALIASES = [GALAXY_ALIAS, "samtools", "slice", "regions", "BED slice", "BAM subset"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("sliced_bam",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-view.html"
    CITATION_DOIS = SAMTOOLS_GALAXY_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_GALAXY_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_GALAXY_CITATION_TEXT
    VERSION = "1.23.1"
    SHELL = True
    OUTPUT_FILENAMES = ("sliced.bam",)
    UPSTREAM_MANPAGE = "doc/samtools-view.1"
    UPSTREAM_SOURCE = "sam_view.c"
    UPSTREAM_SORT_MANPAGE = "doc/samtools-sort.1"
    UPSTREAM_SORT_SOURCE = "bam_sort.c"
    WRAPPER_SOURCE = "tool_collections/samtools/samtools_slice_bam/samtools_slice_bam.xml"
    WRAPPER_GIT_COMMIT = TOOLS_IUC_GIT_COMMIT

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = cls.output_dir(inputs)
        addthreads = str(_additional_threads(inputs))
        cmd = [
            "samtools",
            "view",
            "-@",
            addthreads,
            "-u",
        ]
        slice_method = str(inputs.get("slice_method", "bed"))
        if slice_method == "bed":
            cmd.extend(["-L", str(inputs.get("input_interval", ""))])
        cmd.extend(
            [
                "-X",
                str(inputs.get("input_bam", inputs.get("bam", ""))),
                str(inputs.get("bam_index", "")),
            ]
        )
        if slice_method == "chromosomes":
            cmd.extend(_as_csv_list(inputs.get("refs")))
        elif slice_method == "manual":
            cmd.extend(_as_csv_list(inputs.get("regions")))
        cmd.extend(
            [
                "|",
                "samtools",
                "sort",
                "-O",
                "bam",
                "-T",
                str(output / "tmp"),
                "-@",
                addthreads,
                "-m",
                _sort_memory(inputs),
                "-o",
                str(output / cls.OUTPUT_FILENAMES[0]),
                "-",
            ]
        )
        return cmd

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_colocated_bam_index(inputs, bam_key="input_bam")
        if validation is not True:
            return validation
        slice_method = str(inputs.get("slice_method", "bed"))
        if slice_method == "bed" and not inputs.get("input_interval"):
            return "input_interval is required when slice_method is bed"
        if slice_method == "chromosomes" and not _as_csv_list(inputs.get("refs")):
            return "refs is required when slice_method is chromosomes"
        if slice_method == "manual" and not _as_csv_list(inputs.get("regions")):
            return "regions is required when slice_method is manual"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bam": ("BAM", {"description": "Indexed BAM file to slice"}),
                "bam_index": ("BAI", {"description": "Exact colocated <input_bam>.bai index"}),
                "slice_method": (
                    "STRING",
                    {"default": "bed", "options": ["bed", "chromosomes", "manual"], "description": "Region source"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "input_interval": ("BED", {"description": "BED intervals for slice_method=bed"}),
                "refs": ("STRING_LIST", {"default": [], "description": "Contigs for slice_method=chromosomes"}),
                "regions": (
                    "STRING_LIST",
                    {"default": [], "description": "Manual regions such as chrM:1-1000", "advanced": True},
                ),
                "memory_mb": (
                    "INT",
                    {"default": 768, "min": 1, "description": "Memory per sort thread in MB", "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
