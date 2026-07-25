"""Stable owner for ``vg_call``."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .common import _path_value, _positive_int
from .evidence import PangenomicsCommandContract


class VGCallNode(PangenomicsCommandContract):
    """Call variants from graph alignments with vg."""
    NODE_ID = "vg_call"
    DISPLAY_NAME = "vg Call Variants"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Call variants from graph alignments (GAM) using vg pack + vg call. Produces VCF."
    SEARCH_ALIASES = ["vg", "call", "variant calling", "pangenome", "graph caller"]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("calls_vcf",)
    REQUIRED_EXECUTABLES = ["vg"]
    REQUIRED_CONDA_PACKAGES = ["vg"]
    DOCUMENTATION_URL = "https://github.com/vgteam/vg"
    VERSION = "1.62.0"
    SHELL = True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for name in ("xg_graph", "gam"):
            if not _path_value(inputs.get(name)):
                return f"{name} must be a non-empty path-like value"
        validation = _positive_int(inputs.get("threads", 4), "threads", 4)
        if isinstance(validation, str):
            return validation
        min_support = str(inputs.get("min_support", "") or "")
        if min_support and not re.fullmatch(r"[0-9]+,[0-9]+", min_support):
            return "min_support must use vg's M,N format"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = Path(str(inputs.get("output", ".")))
        pack = out_dir / "aln.pack"
        calls_vcf = out_dir / "calls_vcf.vcf"
        graph = str(inputs.get("xg_graph", ""))
        threads = str(inputs.get("threads", 4))

        cmd = [
            "vg",
            "pack",
            "-x",
            graph,
            "-g",
            str(inputs.get("gam", "")),
            "-o",
            str(pack),
            "-t",
            threads,
            "&&",
            "test",
            "-s",
            str(pack),
            "&&",
            "vg",
            "call",
            graph,
            "-k",
            str(pack),
            "-t",
            threads,
        ]
        if inputs.get("min_support"):
            cmd.extend(["-m", str(inputs["min_support"])])
        if inputs.get("ref_path"):
            cmd.extend(["-p", str(inputs["ref_path"])])
        if inputs.get("sample"):
            cmd.extend(["-s", str(inputs["sample"])])
        cmd.extend([">", str(calls_vcf)])
        cmd.extend(["&&", "test", "-s", str(calls_vcf)])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "calls_vcf.vcf"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "xg_graph": ("FILE", {"description": "Input XG graph index"}),
                "gam": ("FILE", {"description": "Graph alignments in GAM format"}),
                "threads": ("INT", {"default": 4, "min": 1}),
            },
            "optional": {
                "ref_path": ("STRING", {"default": "", "description": "Reference path for VCF coordinates"}),
                "sample": ("STRING", {"default": "", "description": "Sample name for genotype calls"}),
                "min_support": ("STRING", {"default": "", "description": "Minimum allele,site support as M,N"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
