"""CNVkit 0.9.12 scatter and heatmap plotting contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin.cnvkit_family.adapter import (
    CNVKIT_COMMIT,
    CNVkitCommandNode,
    optional_path,
)


class CNVkitPlotNode(CNVkitCommandNode):
    """Create scatter and single-sample heatmap PDFs from CNR/CNS data."""

    NODE_ID = "cnvkit_plot"
    DISPLAY_NAME = "CNVkit Plot"
    DESCRIPTION = "Generate CNVkit scatter and heatmap PDF plots."
    SEARCH_ALIASES = ["cnvkit", "cnv plot", "copy number", "scatter", "heatmap"]
    RETURN_TYPES = ("PDF_REPORT", "PDF_REPORT")
    RETURN_NAMES = ("scatter_plot", "heatmap_plot")
    OUTPUT_FILENAMES = ("scatter_plot.pdf", "heatmap_plot.pdf")
    SOURCE_REF = CNVKIT_COMMIT
    DOCUMENTATION_URL = (
        f"https://github.com/etal/cnvkit/blob/{CNVKIT_COMMIT}/doc/plots.rst"
    )
    UPSTREAM_SCATTER_SOURCE = "cnvlib/scatter.py"
    UPSTREAM_HEATMAP_SOURCE = "cnvlib/heatmap.py"
    SOURCE_PATHS = (
        "cnvlib/commands.py",
        "cnvlib/scatter.py",
        "cnvlib/heatmap.py",
        "doc/plots.rst",
    )
    SOURCE_OUTPUTS = "One explicitly named PDF from scatter and one from heatmap"
    EXIT_SEMANTICS = (
        "Input validation, a non-zero scatter or heatmap command, or either missing "
        "PDF fails the node. Real CNVkit execution was not performed."
    )
    SHELL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "cnr_file": ("FILE", {"description": "CNVkit bin-level ratios (.cnr)"}),
                "cns_file": ("FILE", {"description": "CNVkit segmented ratios (.cns)"}),
            },
            "optional": {
                "chromosome": (
                    "STRING",
                    {"default": "", "description": "Chromosome or chromosomal range"},
                ),
                "gene": (
                    "STRING",
                    {"default": "", "description": "Comma-separated genes for scatter"},
                ),
                "title": ("STRING", {"default": "", "description": "Title applied to both plots"}),
                "by_bin": ("BOOLEAN", {"default": False, "description": "Plot equal-width bins"}),
                "trend": ("BOOLEAN", {"default": False, "description": "Draw the scatter trendline"}),
                "desaturate": ("BOOLEAN", {"default": False, "description": "Desaturate heatmap colors"}),
                "vertical": ("BOOLEAN", {"default": False, "description": "Put samples on the x-axis"}),
                "delimit_samples": (
                    "BOOLEAN",
                    {"default": False, "description": "Draw lines between heatmap samples"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        scatter = [
            "cnvkit.py",
            "scatter",
            str(inputs["cnr_file"]),
            "--segment",
            str(inputs["cns_file"]),
            "--output",
            str(output / cls.OUTPUT_FILENAMES[0]),
        ]
        heatmap = [
            "cnvkit.py",
            "heatmap",
            str(inputs["cns_file"]),
            "--output",
            str(output / cls.OUTPUT_FILENAMES[1]),
        ]

        if inputs.get("chromosome"):
            scatter.extend(["--chromosome", str(inputs["chromosome"])])
            heatmap.extend(["--chromosome", str(inputs["chromosome"])])
        if inputs.get("gene"):
            scatter.extend(["--gene", str(inputs["gene"])])
        if inputs.get("title"):
            scatter.extend(["--title", str(inputs["title"])])
            heatmap.extend(["--title", str(inputs["title"])])
        if inputs.get("by_bin", False):
            scatter.append("--by-bin")
            heatmap.append("--by-bin")
        if inputs.get("trend", False):
            scatter.append("--trend")
        if inputs.get("desaturate", False):
            heatmap.append("--desaturate")
        if inputs.get("vertical", False):
            heatmap.append("--vertical")
        if inputs.get("delimit_samples", False):
            heatmap.append("--delimit-samples")
        return [*scatter, "&&", *heatmap]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("cnr_file", "cns_file"):
            if optional_path(inputs.get(key)) in (None, ""):
                return f"{key} must be a non-empty path-like value"
        for key in ("chromosome", "gene", "title"):
            value = inputs.get(key)
            if value is not None and not isinstance(value, str):
                return f"{key} must be a string"
        return True


__all__ = ["CNVkitPlotNode"]
