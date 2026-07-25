"""DSS 2.58.0 two-group DMR adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import EpigenomicsCommandNode, path_value, safe_output_stem, split_path_list


DSS_DMR_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "dss_dmr.R"


class DSSDMRNode(EpigenomicsCommandNode):
    """Run the documented makeBSseqData, DMLtest, and callDMR sequence."""

    NODE_ID = "dss_dmr"
    DISPLAY_NAME = "DSS DMR"
    DESCRIPTION = "Detect two-group differentially methylated regions from DSS count tables."
    SEARCH_ALIASES = ["DSS", "DMR", "differential methylation", "bisulfite", "methylation", "epigenomics"]
    RETURN_TYPES = ("BED", "TSV")
    RETURN_NAMES = ("dmr", "dmr_stats")
    REQUIRED_EXECUTABLES = ["Rscript"]
    REQUIRED_CONDA_PACKAGES = ["r-base", "bioconductor-dss", "r-readr"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "methylation_files": (
                    "STRING",
                    {"description": "Comma/newline list of tables with chr, pos, N, and X columns"},
                ),
                "sample_info": ("FILE", {"description": "One metadata row per methylation table"}),
                "condition_column": ("STRING", {"default": "condition"}),
                "sample_column": ("STRING", {"default": "sample"}),
            },
            "optional": {
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
                "smoothing": ("BOOLEAN", {"default": True}),
                "delta": ("FLOAT", {"default": 0.1, "min": 0.0, "max": 1.0}),
                "pvalue": ("FLOAT", {"default": 0.001, "min": 0.0, "max": 1.0}),
                "minlen": ("INT", {"default": 50, "min": 1}),
                "mincg": ("INT", {"default": 3, "min": 1}),
                "output_prefix": ("STRING", {"default": "dss_dmr"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if len(split_path_list(inputs.get("methylation_files"))) < 2:
            return "At least two methylation files are required"
        if path_value(inputs.get("sample_info")) is None:
            return "sample_info is required"
        for field in ("condition_column", "sample_column"):
            if not str(inputs.get(field, "")).strip():
                return f"{field} is required"
        if int(inputs.get("threads", 1)) < 1:
            return "threads must be at least 1"
        if not 0 <= float(inputs.get("delta", 0.1)) <= 1:
            return "delta must be between 0 and 1"
        if not 0 < float(inputs.get("pvalue", 0.001)) <= 1:
            return "pvalue must be greater than 0 and at most 1"
        if int(inputs.get("minlen", 50)) < 1:
            return "minlen must be at least 1"
        if int(inputs.get("mincg", 3)) < 1:
            return "mincg must be at least 1"
        return True

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
        stem = safe_output_stem(inputs.get("output_prefix"), "dss_dmr")
        out_dir = Path(output_dir)
        return out_dir / f"{stem}.dmr.bed", out_dir / f"{stem}.dmr_stats.tsv"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return list(cls._output_paths(inputs, node_out))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        output_bed, output_stats = cls._output_paths(inputs, inputs.get("output", "."))
        cmd = [
            "Rscript",
            str(DSS_DMR_SCRIPT),
            "--methylation-files",
            ",".join(split_path_list(inputs.get("methylation_files"))),
            "--sample-info",
            str(inputs["sample_info"]),
            "--condition-column",
            str(inputs.get("condition_column", "condition")),
            "--sample-column",
            str(inputs.get("sample_column", "sample")),
            "--threads",
            str(inputs.get("threads", 1)),
            "--output-bed",
            str(output_bed),
            "--output-stats",
            str(output_stats),
            "--delta",
            str(inputs.get("delta", 0.1)),
            "--pvalue",
            str(inputs.get("pvalue", 0.001)),
            "--minlen",
            str(inputs.get("minlen", 50)),
            "--mincg",
            str(inputs.get("mincg", 3)),
        ]
        if inputs.get("smoothing", True):
            cmd.append("--smoothing")
        return cmd
