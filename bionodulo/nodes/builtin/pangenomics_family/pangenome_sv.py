"""Stable owner for ``pangenome_sv``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import _non_negative_int, _path_value, _positive_int
from .evidence import PangenomicsCommandContract


class PangenomeSVNode(PangenomicsCommandContract):
    """Call structural variants from a pangenome graph against a reference path."""

    NODE_ID = "pangenome_sv"
    DISPLAY_NAME = "Pangenome SV"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Call structural variants from a pangenome graph against a reference and emit an indexed VCF."
    SEARCH_ALIASES = ["pangenome", "structural variants", "sv", "graph vcf", "pangenome graph", "vg deconstruct"]
    RETURN_TYPES = ("VCF_GZ", "VCF_INDEX")
    RETURN_NAMES = ("sv_vcf", "sv_vcf_index")
    REQUIRED_EXECUTABLES = ["vg", "bcftools", "bgzip", "tabix"]
    REQUIRED_CONDA_PACKAGES = ["vg", "bcftools", "htslib"]
    DOCUMENTATION_URL = "https://github.com/vgteam/vg"
    VERSION = "1.62.0"
    SHELL = True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if not _path_value(inputs.get("graph_gfa")):
            return "graph_gfa must be a non-empty path-like value"
        if not str(inputs.get("ref_path", "") or "").strip():
            return "ref_path is required"
        validation = _positive_int(inputs.get("threads", 8), "threads", 8)
        if isinstance(validation, str):
            return validation
        validation = _non_negative_int(inputs.get("min_sv_length", 50), "min_sv_length", 50)
        if isinstance(validation, str):
            return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        xg_index = out_dir / "graph.xg"
        output_vcf = out_dir / "sv_vcf.vcf.gz"
        threads = int(inputs.get("threads", 8) or 8)
        min_sv_length = int(inputs.get("min_sv_length", 0) or 0)

        cmd: list[str] = [
            "vg",
            "convert",
            "-x",
            str(inputs.get("graph_gfa", "")),
            ">",
            str(xg_index),
            "&&",
            "vg",
            "deconstruct",
            "-P",
            str(inputs.get("ref_path", "")),
            "-a",
            "-t",
            str(threads),
            str(xg_index),
        ]

        if min_sv_length > 0:
            cmd.extend([
                "|",
                "bcftools",
                "view",
                "-i",
                f"ABS(ILEN)>={min_sv_length} || ABS(strlen(ALT)-strlen(REF))>={min_sv_length}",
            ])
        cmd.extend(["|", "bgzip"])
        cmd.extend(["--threads", str(threads)])
        cmd.extend([
            "-c",
            ">",
            str(output_vcf),
            "&&",
            "tabix",
            "-f",
            "-p",
            "vcf",
            str(output_vcf),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        vcf = node_out / "sv_vcf.vcf.gz"
        return [vcf, Path(f"{vcf}.tbi")]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "graph_gfa": ("GFA", {"description": "Input pangenome graph in GFA format"}),
                "ref_path": ("STRING", {"description": "Reference path prefix passed to vg deconstruct -P"}),
            },
            "optional": {
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
                "min_sv_length": ("INT", {"default": 50, "min": 0, "description": "Minimum variant length to keep"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
