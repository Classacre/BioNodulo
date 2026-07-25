"""Stable owner for ``vcf_decompose``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import _non_negative_int, _path_value, _positive_int
from .evidence import PangenomicsCommandContract


class VCFDecomposeNode(PangenomicsCommandContract):
    """Decompose complex pangenome VCF records into primitive alleles."""

    NODE_ID = "vcf_decompose"
    DISPLAY_NAME = "VCF Decompose"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Decompose complex variants in a pangenome VCF into primitive, normalized records."
    SEARCH_ALIASES = ["vcf", "decompose", "pangenome vcf", "primitive variants", "vcflib", "normalize"]
    RETURN_TYPES = ("VCF_GZ", "VCF_INDEX")
    RETURN_NAMES = ("decomposed_vcf", "decomposed_vcf_index")
    REQUIRED_EXECUTABLES = ["vcfwave", "vcfallelicprimitives", "bgzip", "tabix"]
    REQUIRED_CONDA_PACKAGES = ["vcflib", "htslib"]
    DOCUMENTATION_URL = "https://github.com/vcflib/vcflib"
    VERSION = "1.0.9"
    SHELL = True

    _MODES = {"decompose", "normalize"}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        mode = str(inputs.get("mode", "normalize") or "normalize")
        if mode not in cls._MODES:
            return f"Unsupported VCF decompose mode: {mode}"
        if not _path_value(inputs.get("vcf")):
            return "vcf must be a non-empty path-like value"
        validation = _positive_int(inputs.get("threads", 1), "threads", 1)
        if isinstance(validation, str):
            return validation
        validation = _non_negative_int(inputs.get("max_length", 0), "max_length")
        if isinstance(validation, str):
            return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        output_vcf = out_dir / "decomposed_vcf.vcf.gz"
        mode = str(inputs.get("mode", "normalize") or "normalize")
        threads = int(inputs.get("threads", 1) or 1)
        max_length = int(inputs.get("max_length", 0) or 0)

        if mode == "normalize":
            cmd = ["vcfwave", "--threads", str(threads)]
            if max_length:
                cmd.extend(["--max-length", str(max_length)])
            cmd.append(str(inputs.get("vcf", "")))
        else:
            cmd = ["vcfallelicprimitives"]
            if inputs.get("keep_info"):
                cmd.append("--keep-info")
            if max_length:
                cmd.extend(["--max-length", str(max_length)])
            cmd.append(str(inputs.get("vcf", "")))

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
        vcf = node_out / "decomposed_vcf.vcf.gz"
        return [vcf, Path(f"{vcf}.tbi")]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("FILE", {"description": "Plain or compressed complex-variant VCF"}),
            },
            "optional": {
                "mode": (
                    "STRING",
                    {
                        "default": "normalize",
                        "options": ["decompose", "normalize"],
                        "description": "normalize uses recommended vcfwave; decompose uses legacy vcfallelicprimitives",
                    },
                ),
                "keep_info": (
                    "BOOLEAN",
                    {"default": False, "description": "Legacy primitives only; vcfwave ignores keep-info"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64, "display": "slider"}),
                "max_length": ("INT", {"default": 0, "min": 0, "description": "0 means unlimited"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
