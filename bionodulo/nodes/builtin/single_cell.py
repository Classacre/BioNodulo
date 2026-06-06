"""Single-cell analysis nodes for BioNodulo.

Provides nodes for 10x Genomics Cell Ranger count and reference building.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


class CellRangerCountNode(CommandNode):
    """Run Cell Ranger count for 10x Genomics scRNA-seq."""
    NODE_ID = "cellranger_count"
    DISPLAY_NAME = "Cell Ranger Count"
    REQUIRED_CONDA_PACKAGES = ['cellranger']
    CATEGORY = "single_cell"
    DESCRIPTION = "Align 10x Genomics scRNA-seq reads and generate feature-barcode matrix"
    SEARCH_ALIASES = ["cellranger", "10x", "scrna", "count", "single cell"]
    RETURN_TYPES = ("CELL_RANGER_OUT", "FILE", "CSV", "DIRECTORY", "FILE", "DIRECTORY", "FILE")
    RETURN_NAMES = (
        "output_dir",
        "web_summary",
        "metrics_summary",
        "filtered_feature_bc_matrix",
        "filtered_feature_bc_matrix_h5",
        "raw_feature_bc_matrix",
        "raw_feature_bc_matrix_h5",
    )
    REQUIRED_EXECUTABLES = ["cellranger"]
    DOCUMENTATION_URL = "https://www.10xgenomics.com/support/software/cell-ranger"
    VERSION = "9.0.1"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        # Cell Ranger writes outputs under `<output_dir>/<run_id>/outs/`.
        # We expose the full run directory for downstream tools, plus key
        # Cell Ranger report artifacts that templates can validate and preview.
        od = Path(output_dir) / cls.NODE_ID
        run_id = str(inputs.get("run_id", "cellranger_count"))
        outs = od / run_id / "outs"
        return [
            od / run_id,
            outs / "web_summary.html",
            outs / "metrics_summary.csv",
            outs / "filtered_feature_bc_matrix",
            outs / "filtered_feature_bc_matrix.h5",
            outs / "raw_feature_bc_matrix",
            outs / "raw_feature_bc_matrix.h5",
        ]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "cellranger", "count",
            "--id", str(inputs.get("run_id", "cellranger_count")),
            "--transcriptome", str(inputs.get("transcriptome", "")),
            "--fastqs", str(inputs.get("fastq_dir", "")),
            "--localcores", str(inputs.get("threads", 16)),
            "--localmem", str(inputs.get("memory", 64)),
        ]
        if inputs.get("sample"):
            cmd.extend(["--sample", str(inputs["sample"])])
        if inputs.get("expect_cells"):
            cmd.extend(["--expect-cells", str(inputs["expect_cells"])])
        if inputs.get("chemistry"):
            cmd.extend(["--chemistry", str(inputs["chemistry"])])
        if inputs.get("lanes"):
            cmd.extend(["--lanes", str(inputs["lanes"])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fastq_dir": ("DIRECTORY", {"description": "Directory with FASTQ files"}),
                "transcriptome": ("DIRECTORY", {"description": "Cell Ranger reference transcriptome"}),
                "threads": ("INT", {"default": 16, "min": 1, "max": 64, "display": "slider"}),
                "memory": ("INT", {"default": 64, "min": 8, "description": "Memory in GB"}),
                "run_id": ("STRING", {"default": "cellranger_count"}),
            },
            "optional": {
                "sample": ("STRING", {"description": "Sample name matching FASTQ files"}),
                "expect_cells": ("INT", {"default": 3000, "min": 100, "max": 50000, "step": 100, "display": "slider"}),
                "chemistry": ("STRING", {"default": "auto", "description": "Chemistry assay configuration", "advanced": True}),
                "lanes": ("STRING", {"default": "", "description": "Lanes to analyze", "advanced": True}),
            },
            "hidden": {},
        }


class CellRangerMkrefNode(CommandNode):
    """Build Cell Ranger reference transcriptome."""
    NODE_ID = "cellranger_mkref"
    DISPLAY_NAME = "Cell Ranger mkref"
    REQUIRED_CONDA_PACKAGES = ['cellranger']
    CATEGORY = "single_cell"
    DESCRIPTION = "Build a Cell Ranger compatible reference transcriptome"
    SEARCH_ALIASES = ["cellranger", "mkref", "reference", "transcriptome", "10x"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("reference",)
    REQUIRED_EXECUTABLES = ["cellranger"]
    DOCUMENTATION_URL = "https://www.10xgenomics.com/support/software/cell-ranger"
    VERSION = "9.0.1"
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
            "hidden": {
                "output": ("STRING", {}),
            },
        }
