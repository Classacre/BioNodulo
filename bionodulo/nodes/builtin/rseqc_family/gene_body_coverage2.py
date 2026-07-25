"""RSeQC 5.0.3 ``geneBody_coverage2.py`` node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import RSeQCCommandNode


class RSeQCGeneBodyCoverage2Node(RSeQCCommandNode):
    """Measure gene-body coverage from a BigWig signal track."""

    NODE_ID = "rseqc_gene_body_coverage2"
    DISPLAY_NAME = "RSeQC Gene Body Coverage BigWig"
    DESCRIPTION = "Calculate RNA-seq gene-body coverage from a BigWig signal file."
    SEARCH_ALIASES = ["BioNodulo builtin", "RSeQC", "geneBody_coverage2", "gene body coverage BigWig"]
    RETURN_TYPES = ("TSV", "TEXT", "IMAGE")
    RETURN_NAMES = ("coverage_table", "r_script", "coverage_plot")
    REQUIRED_EXECUTABLES = ["geneBody_coverage2.py", "Rscript"]
    REQUIRED_CONDA_PACKAGES = ["rseqc", "r-base"]
    UPSTREAM_SCRIPT = "scripts/geneBody_coverage2.py"
    UPSTREAM_SOURCE = UPSTREAM_SCRIPT
    UPSTREAM_OUTPUT_SOURCE = "scripts/geneBody_coverage2.py:coverageGeneBody_bigwig"
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#genebody-coverage2-py"

    GRAPH_TYPES = ("pdf", "png", "bmp", "jpeg", "tiff")
    REQUIRED_PATH_INPUTS = ("input", "refgene")
    OUTPUT_FILENAMES = (
        "output.geneBodyCoverage.txt",
        "output.geneBodyCoverage_plot.r",
        "output.geneBodyCoverage.pdf",
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BIGWIG", {"description": "Coverage signal file in BigWig format"}),
                "refgene": ("BED", {"description": "Reference gene model in BED format"}),
            },
            "optional": {
                "graph_type": (
                    "STRING",
                    {"default": "pdf", "options": list(cls.GRAPH_TYPES), "description": "R graph file type"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        graph_type = str(inputs.get("graph_type", "pdf")).lower()
        return [
            node_dir / "output.geneBodyCoverage.txt",
            node_dir / "output.geneBodyCoverage_plot.r",
            node_dir / f"output.geneBodyCoverage.{graph_type}",
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if "rscript_output" in inputs:
            return "Legacy input 'rscript_output' is unsupported; the source always creates its R script"
        return cls.validate_choice(inputs.get("graph_type", "pdf"), cls.GRAPH_TYPES, "graph_type")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return cls.checked_command(
            inputs,
            "geneBody_coverage2.py",
            "-i",
            str(inputs["input"]),
            "-r",
            str(inputs["refgene"]),
            "-o",
            str(cls.output_prefix(inputs, "output")),
            "-t",
            str(inputs.get("graph_type", "pdf")),
        )
