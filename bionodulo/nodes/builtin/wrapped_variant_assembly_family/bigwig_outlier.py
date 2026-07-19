"""Focused bigwig outlier node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

class BigWigOutlierBedNode(CommandNode):
    """Convert high, low, or zero BigWig outlier runs into BED features."""

    NODE_ID = "bigwig_outlier_bed"
    DISPLAY_NAME = "Bigwig outliers to bed features"
    REQUIRED_CONDA_PACKAGES = ["python", "numpy", "pybigtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Write continuous high, low, or zero-valued BigWig outlier regions as BED features, with optional contig statistics."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BigWig outliers",
        "bigwig_outlier_bed",
        "pybigtools",
        "coverage outliers",
        "BED features",
        "quantile cutoff",
        "contig statistics",
    ]
    RETURN_TYPES = ("BED", "BED", "BED", "BED", "TXT")
    RETURN_NAMES = ("high_low_bed", "high_bed", "low_bed", "zero_bed", "contig_statistics")
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://github.com/jackh726/bigtools"
    CITATION_DOIS = ["10.1093/bioinformatics/btae350"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/btae350"]
    CITATION_TEXT = "Bigtools: a high-performance toolkit for BigWig and BigBed files."
    VERSION = "0.2.5"
    SHELL = True

    BED_OUTPUTS = {
        "bedouthilo": "high_low_regions.bed",
        "bedouthi": "high_regions.bed",
        "bedoutlo": "low_regions.bed",
        "bedoutzero": "zero_regions.bed",
    }

    @classmethod
    def _output_names(cls, outbeds: str) -> list[str]:
        if outbeds == "outhilo":
            return ["bedouthilo"]
        if outbeds == "outhi":
            return ["bedouthi"]
        if outbeds == "outlo":
            return ["bedoutlo"]
        if outbeds == "outzero":
            return ["bedoutzero"]
        if outbeds == "outall":
            return ["bedouthilo", "bedouthi", "bedoutlo"]
        if outbeds == "outlohi":
            return ["bedouthi", "bedoutlo"]
        return []

    @classmethod
    def _bigwig_labels(cls, inputs: dict[str, Any], bigwigs: list[str]) -> list[str]:
        labels = _as_list(inputs.get("bigwiglabels"))
        if labels:
            return labels
        return [Path(bigwig).name for bigwig in bigwigs]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        bigwigs = _as_list(inputs.get("bigwig"))
        cmd = ["python", str(inputs.get("script", "bigwig_outlier_bed.py"))]
        for bigwig in bigwigs:
            cmd.extend(["--bigwig", bigwig])
        for label in cls._bigwig_labels(inputs, bigwigs):
            cmd.extend(["--bigwiglabels", label])
        outbeds = str(inputs.get("outbeds", "outhilo"))
        cmd.extend(["--outbeds", outbeds])
        for output_name in cls._output_names(outbeds):
            cmd.extend([f"--{output_name}", f"{out}/{cls.BED_OUTPUTS[output_name]}"])
        cmd.extend(["--minwin", str(inputs.get("minwin", 10))])
        if inputs.get("qhi") is not None and str(inputs.get("qhi")) != "":
            cmd.extend(["--qhi", str(inputs.get("qhi"))])
        if inputs.get("qlo") is not None and str(inputs.get("qlo")) != "":
            cmd.extend(["--qlo", str(inputs.get("qlo"))])
        if str(inputs.get("tableout", "create")) == "create" or outbeds == "outtab":
            cmd.extend(["--tableoutfile", f"{out}/contig_statistics.txt"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outbeds = str(inputs.get("outbeds", "outhilo"))
        outputs = [out / cls.BED_OUTPUTS[output_name] for output_name in cls._output_names(outbeds)]
        if str(inputs.get("tableout", "create")) == "create" or outbeds == "outtab":
            outputs.append(out / "contig_statistics.txt")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        outbed_options = ["outhilo", "outhi", "outlo", "outzero", "outall", "outlohi", "outtab"]
        return {
            "required": {
                "bigwig": (
                    "BIGWIG",
                    {
                        "multiple": True,
                        "description": "One or more BigWig files sharing the same reference sequence",
                    },
                ),
            },
            "optional": {
                "bigwiglabels": (
                    "STRING",
                    {"default": [], "multiple": True, "description": "Optional labels aligned to the BigWig inputs"},
                ),
                "minwin": (
                    "INT",
                    {
                        "default": 10,
                        "min": 1,
                        "description": "Minimum continuous bases required for a BED feature",
                    },
                ),
                "qhi": (
                    "FLOAT",
                    {"default": 0.99999, "min": 0, "max": 1, "description": "Upper quantile cutoff for high regions"},
                ),
                "qlo": (
                    "FLOAT",
                    {"default": 0.00001, "min": 0, "max": 1, "description": "Lower quantile cutoff for low regions"},
                ),
                "outbeds": (
                    "STRING",
                    {
                        "default": "outhilo",
                        "options": outbed_options,
                        "description": "Select high/low/zero BED outputs or table-only mode",
                    },
                ),
                "tableout": (
                    "STRING",
                    {
                        "default": "create",
                        "options": ["create", "donotmake"],
                        "description": "Whether to write the contig statistics table",
                    },
                ),
                "script": (
                    "FILE",
                    {
                        "default": "bigwig_outlier_bed.py",
                        "advanced": True,
                        "description": "Path to the Galaxy bigwig_outlier_bed.py helper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(BigWigOutlierBedNode)

__all__ = ['BigWigOutlierBedNode']
