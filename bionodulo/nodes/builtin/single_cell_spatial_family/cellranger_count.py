"""10x Genomics Cell Ranger 9.0.1 count contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from .adapter import path_value, validate_int, validate_run_id


class CellRangerCountNode(CommandNode):
    """Run the licensed Cell Ranger count binary in a deterministic node directory."""

    NODE_ID = "cellranger_count"
    DISPLAY_NAME = "Cell Ranger Count"
    CATEGORY = "single_cell"
    DESCRIPTION = "Run 10x Genomics Cell Ranger count and expose its native feature-barcode outputs."
    SEARCH_ALIASES = ["BioNodulo builtin", "Cell Ranger", "10x", "scRNA-seq", "count", "single cell"]
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
    REQUIRED_CONDA_PACKAGES: list[str] = []
    VERSION = "9.0.1"
    DOCUMENTATION_URL = (
        "https://www.10xgenomics.com/support/software/cell-ranger/9.0/analysis/running-pipelines/cr-gex-count"
    )
    RELEASE_NOTES_URL = "https://www.10xgenomics.com/support/software/cell-ranger/9.0/release-notes"
    DISTRIBUTION = "Licensed 10x Genomics Cell Ranger 9.0.1 binary; not available from Bioconda/conda-forge."
    UPSTREAM_SOURCE = "10x Cell Ranger 9.0 count documentation and 9.0.1 release notes"
    PACKAGE_CONSTRAINT = "external binary cellranger 9.0.1"
    EXIT_SEMANTICS = "Cell Ranger exit code 0 plus every declared native output is success; non-zero fails."
    RUN_IN_NODE_OUTPUT_DIR = True
    SHELL = False
    ENV_VARS = {"TENX_DISABLE_TELEMETRY": "1"}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fastq_dir": ("DIRECTORY", {"description": "Directory containing Cell Ranger-compatible FASTQs"}),
                "transcriptome": ("DIRECTORY", {"description": "Cell Ranger reference transcriptome"}),
                "threads": ("INT", {"default": 16, "min": 1, "max": 64}),
                "memory": ("INT", {"default": 64, "min": 8, "description": "Local memory in GiB"}),
                "run_id": ("STRING", {"default": "cellranger_count"}),
            },
            "optional": {
                "sample": ("STRING", {"default": "", "description": "FASTQ sample prefix(es), comma-separated"}),
                "expect_cells": ("INT", {"default": None, "min": 1}),
                "create_bam": ("BOOLEAN", {"default": False}),
            },
            "hidden": {},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        run_dir = node_dir / str(inputs.get("run_id", "cellranger_count"))
        outs = run_dir / "outs"
        node_dir.mkdir(parents=True, exist_ok=True)
        return [
            run_dir,
            outs / "web_summary.html",
            outs / "metrics_summary.csv",
            outs / "filtered_feature_bc_matrix",
            outs / "filtered_feature_bc_matrix.h5",
            outs / "raw_feature_bc_matrix",
            outs / "raw_feature_bc_matrix.h5",
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("fastq_dir", "transcriptome"):
            if not path_value(inputs.get(key)):
                return f"Input '{key}' must be a non-empty path-like value"
        validation = validate_run_id(inputs.get("run_id", "cellranger_count"))
        if validation is not True:
            return validation
        validation = validate_int(inputs.get("threads", 16), "threads", minimum=1, maximum=64)
        if validation is not True:
            return validation
        validation = validate_int(inputs.get("memory", 64), "memory", minimum=8)
        if validation is not True:
            return validation
        if inputs.get("expect_cells") is not None:
            validation = validate_int(inputs["expect_cells"], "expect_cells", minimum=1)
            if validation is not True:
                return validation
        sample = str(inputs.get("sample", "") or "")
        if sample and any(not part for part in sample.split(",")):
            return "Input 'sample' must contain non-empty comma-separated prefixes"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = [
            "cellranger",
            "count",
            "--id",
            str(inputs.get("run_id", "cellranger_count")),
            "--transcriptome",
            path_value(inputs.get("transcriptome")),
            "--fastqs",
            path_value(inputs.get("fastq_dir")),
            "--localcores",
            str(inputs.get("threads", 16)),
            "--localmem",
            str(inputs.get("memory", 64)),
        ]
        if inputs.get("sample") not in (None, ""):
            command.extend(["--sample", str(inputs["sample"])])
        if inputs.get("expect_cells") is not None:
            command.extend(["--expect-cells", str(inputs["expect_cells"])])
        command.append(f"--create-bam={'true' if inputs.get('create_bam', False) else 'false'}")
        return command
