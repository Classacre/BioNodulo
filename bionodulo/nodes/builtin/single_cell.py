"""Single-cell analysis nodes for BioNodulo.

Provides nodes for 10x Genomics Cell Ranger count and reference building.
"""
from __future__ import annotations

from typing import Any

from bionodulo.nodes.command_node import CommandNode


class CellRangerCountNode(CommandNode):
    """Run Cell Ranger count for 10x Genomics scRNA-seq."""
    NODE_ID = "cellranger_count"
    DISPLAY_NAME = "Cell Ranger Count"
    CATEGORY = "single_cell"
    DESCRIPTION = "Align 10x Genomics scRNA-seq reads and generate feature-barcode matrix"
    SEARCH_ALIASES = ["cellranger", "10x", "scrna", "count", "single cell"]
    RETURN_TYPES = ("CELL_RANGER_OUT",)
    RETURN_NAMES = ("output_dir",)
    REQUIRED_EXECUTABLES = ["cellranger"]
    DOCUMENTATION_URL = "https://www.10xgenomics.com/support/software/cell-ranger"
    VERSION = "8.0"
    COMMAND = [
        "cellranger", "count",
        "--id", "{inputs.run_id}",
        "--transcriptome", "{inputs.transcriptome}",
        "--fastqs", "{inputs.fastq_dir}",
        "--sample", "{inputs.sample}",
        "--localcores", "{inputs.threads}",
        "--localmem", "{inputs.memory}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fastq_dir": ("DIRECTORY", {"description": "Directory with FASTQ files"}),
                "transcriptome": ("DIRECTORY", {"description": "Cell Ranger reference transcriptome"}),
                "sample": ("STRING", {"description": "Sample name matching FASTQ files"}),
                "threads": ("INT", {"default": 16, "min": 1, "max": 64, "display": "slider"}),
                "memory": ("INT", {"default": 64, "min": 8, "description": "Memory in GB"}),
                "run_id": ("STRING", {"default": "cellranger_count"}),
            },
            "optional": {
                "expect_cells": ("INT", {"default": 3000, "min": 100, "max": 50000, "step": 100, "display": "slider"}),
            },
            "hidden": {},
        }


class CellRangerMkrefNode(CommandNode):
    """Build Cell Ranger reference transcriptome."""
    NODE_ID = "cellranger_mkref"
    DISPLAY_NAME = "Cell Ranger mkref"
    CATEGORY = "single_cell"
    DESCRIPTION = "Build a Cell Ranger compatible reference transcriptome"
    SEARCH_ALIASES = ["cellranger", "mkref", "reference", "transcriptome", "10x"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("reference",)
    REQUIRED_EXECUTABLES = ["cellranger"]
    DOCUMENTATION_URL = "https://www.10xgenomics.com/support/software/cell-ranger"
    VERSION = "8.0"
    COMMAND = [
        "cellranger", "mkref",
        "--genome={inputs.genome_name}",
        "--fasta={inputs.fasta}",
        "--genes={inputs.gtf}",
        "--nthreads={inputs.threads}",
        "--memgb={inputs.memory}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fasta": ("FASTA", {"description": "Reference genome FASTA"}),
                "gtf": ("GTF", {"description": "Gene annotation GTF"}),
                "genome_name": ("STRING", {"default": "custom_ref"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
                "memory": ("INT", {"default": 32, "min": 8, "description": "Memory in GB"}),
            },
            "optional": {},
            "hidden": {},
        }
