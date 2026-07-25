"""Focused Samtools 1.23.1 owner: Galaxy wrapper parity node for SAM-to-BAM conversion."""

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
    TOOLS_IUC_GIT_COMMIT,
    TOOLS_IUC_GIT_URL,
)


class GalaxySamToBamNode(SamtoolsCommandNode):
    """Galaxy wrapper parity node for SAM-to-BAM conversion."""

    NODE_ID = "sam_to_bam"
    DISPLAY_NAME = "SAM-to-BAM"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Convert a SAM dataset into sorted BAM format using the Galaxy SAM-to-BAM wrapper."
    SEARCH_ALIASES = [
        GALAXY_ALIAS,
        "samtools",
        "sam_to_bam",
        "SAM-to-BAM",
        "SAM to BAM",
        "converted BAM",
        "reference sequence",
    ]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("output1",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tool_collections/samtools/sam_to_bam"
    CITATION_DOIS = SAMTOOLS_GALAXY_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_GALAXY_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_GALAXY_CITATION_TEXT
    VERSION = "2.1.5"
    GIT_URL = TOOLS_IUC_GIT_URL
    GIT_COMMIT = TOOLS_IUC_GIT_COMMIT
    SHELL = True
    REFERENCE_OPTIONS = ["history", "cached"]
    OUTPUT_FILENAMES = ("output1.bam",)
    UPSTREAM_MANPAGE = "doc/samtools-view.1"
    UPSTREAM_SOURCE = "sam_view.c"
    UPSTREAM_SORT_MANPAGE = "doc/samtools-sort.1"
    UPSTREAM_SORT_SOURCE = "bam_sort.c"
    WRAPPER_SOURCE = "tool_collections/samtools/sam_to_bam/sam_to_bam.xml"

    @classmethod
    def _reference_setup_and_index(cls, inputs: dict[str, Any]) -> tuple[list[str], str]:
        addref_select = str(inputs.get("addref_select", "history") or "history")
        if addref_select == "cached":
            return [], str(inputs.get("cached_ref_index", ""))
        return [], str(inputs.get("ref_index", ""))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = cls.output_dir(inputs)
        setup, reference_index = cls._reference_setup_and_index(inputs)
        addthreads = str(_additional_threads(inputs))
        return [
            *setup,
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
        addref_select = str(inputs.get("addref_select", "history") or "history")
        if addref_select not in cls.REFERENCE_OPTIONS:
            return f"addref_select must be one of: {', '.join(cls.REFERENCE_OPTIONS)}"
        if addref_select == "history" and not str(inputs.get("ref", "") or "").strip():
            return "ref is required when addref_select is history"
        if addref_select == "cached" and not str(inputs.get("cached_ref_path", "") or "").strip():
            return "cached_ref_path is required when addref_select is cached"
        if addref_select == "history":
            return validate_colocated_reference_index(
                inputs,
                reference_key="ref",
                index_key="ref_index",
            )
        return validate_colocated_reference_index(
            inputs,
            reference_key="cached_ref_path",
            index_key="cached_ref_index",
        )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("SAM", {"description": "SAM file to convert to BAM"}),
                "addref_select": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.REFERENCE_OPTIONS,
                        "description": "Use a reference FASTA from history or a cached built-in reference",
                    },
                ),
            },
            "optional": {
                "ref": ("FASTA", {"description": "Reference FASTA used when addref_select is history"}),
                "ref_index": (
                    "FASTA_INDEX",
                    {"description": "Exact colocated <ref>.fai index for a history reference"},
                ),
                "cached_ref_path": (
                    "FASTA",
                    {
                        "description": "Path to cached reference FASTA used when addref_select is cached",
                        "advanced": True,
                    },
                ),
                "cached_ref_index": (
                    "FASTA_INDEX",
                    {"description": "Exact colocated cached reference .fai index", "advanced": True},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64, "display": "slider"}),
                "memory_mb": (
                    "INT",
                    {"default": 768, "min": 1, "description": "Memory per sort thread in MB", "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
