"""Focused preseq node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

class PreseqCCurveNode(CommandNode):
    """Estimate sequencing-library complexity curves with preseq c_curve."""

    NODE_ID = "preseq_c_curve"
    DISPLAY_NAME = "Preseq c_curve"
    REQUIRED_CONDA_PACKAGES = ["preseq"]
    CATEGORY = "qc"
    DESCRIPTION = "Estimate a sequencing library complexity curve from a coordinate-sorted BAM file."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Preseq",
        "preseq c_curve",
        "library complexity",
        "sequencing saturation",
        "distinct reads",
        "duplicate complexity",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("complexity_curve",)
    REQUIRED_EXECUTABLES = ["preseq"]
    DOCUMENTATION_URL = "https://smithlabresearch.org/software/preseq/"
    CITATION_DOIS = ["10.1038/nmeth.2375"]
    CITATION_URLS = [f"{DOI_URL}10.1038/nmeth.2375"]
    CITATION_TEXT = "Predicting the molecular complexity of sequencing libraries."
    VERSION = "3.2.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        staged_bam = f"{out}/input.bam"
        cmd = [
            "ln",
            "-sf",
            str(inputs.get("input_bam", "")),
            staged_bam,
            "&&",
            "preseq",
            "c_curve",
            "-B",
            staged_bam,
        ]
        if inputs.get("verbose"):
            cmd.append("-v")
        cmd.extend(["-s", str(inputs.get("step_size", 1000))])
        _add_if_value(cmd, "-l", inputs.get("max_read_len"))
        cmd.extend(["-o", f"{out}/complexity_curve.tsv"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "complexity_curve.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bam": ("BAM", {"description": "Coordinate-sorted BAM file"}),
                "step_size": ("INT", {"default": 1000, "min": 100, "description": "Step size for complexity curve calculation"}),
            },
            "optional": {
                "max_read_len": ("INT", {"default": "", "min": 1, "description": "Optional maximum read length to consider"}),
                "verbose": ("BOOLEAN", {"default": False, "description": "Print verbose preseq diagnostics"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class PreseqLCExtrapNode(CommandNode):
    """Extrapolate sequencing-library yield curves with preseq lc_extrap."""

    NODE_ID = "preseq_lc_extrap"
    DISPLAY_NAME = "Preseq lc_extrap"
    REQUIRED_CONDA_PACKAGES = ["preseq"]
    CATEGORY = "qc"
    DESCRIPTION = "Predict additional distinct reads from deeper sequencing of a coordinate-sorted BAM library."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Preseq",
        "preseq lc_extrap",
        "yield extrapolation",
        "library complexity",
        "future sequencing",
        "distinct read yield",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("yield_extrapolation",)
    REQUIRED_EXECUTABLES = ["preseq"]
    DOCUMENTATION_URL = "https://smithlabresearch.org/software/preseq/"
    CITATION_DOIS = ["10.1038/nmeth.2375"]
    CITATION_URLS = [f"{DOI_URL}10.1038/nmeth.2375"]
    CITATION_TEXT = "Predicting the molecular complexity of sequencing libraries."
    VERSION = "3.2.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        staged_bam = f"{out}/input.bam"
        cmd = [
            "ln",
            "-sf",
            str(inputs.get("input_bam", "")),
            staged_bam,
            "&&",
            "preseq",
            "lc_extrap",
            "-B",
            staged_bam,
        ]
        if inputs.get("verbose"):
            cmd.append("-v")
        cmd.extend([
            "-e",
            str(inputs.get("extrap_limit", 10000000)),
            "-s",
            str(inputs.get("step_size", 100000)),
            "-o",
            f"{out}/yield_extrapolation.tsv",
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "yield_extrapolation.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bam": ("BAM", {"description": "Coordinate-sorted BAM file"}),
                "extrap_limit": ("INT", {"default": 10000000, "min": 1, "description": "Total reads to extrapolate to"}),
                "step_size": ("INT", {"default": 100000, "min": 1, "description": "Step size for yield extrapolation"}),
            },
            "optional": {
                "verbose": ("BOOLEAN", {"default": False, "description": "Print verbose preseq diagnostics"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(PreseqCCurveNode)
pin_contract(PreseqLCExtrapNode)

__all__ = ['PreseqCCurveNode', 'PreseqLCExtrapNode']
