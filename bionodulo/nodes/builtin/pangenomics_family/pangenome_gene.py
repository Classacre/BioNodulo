"""Stable owner for ``pangenome_gene``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import _positive_int, _split_path_list
from .evidence import PangenomicsCommandContract


class PangenomeGeneNode(PangenomicsCommandContract):
    """Extract gene presence/absence matrices from pangenome annotations."""

    NODE_ID = "pangenome_gene"
    DISPLAY_NAME = "Pangenome Gene"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Extract gene presence/absence matrix and summary plot from pangenome annotations."
    SEARCH_ALIASES = ["pangenome", "panaroo", "presence absence", "orthologs", "gene clusters"]
    RETURN_TYPES = ("FILE", "IMAGE")
    RETURN_NAMES = ("presence_matrix", "pan_genome_plot")
    REQUIRED_EXECUTABLES = ["panaroo"]
    REQUIRED_CONDA_PACKAGES = ["panaroo"]
    DOCUMENTATION_URL = "https://github.com/gtonkinhill/panaroo"
    VERSION = "1.5.0"
    SHELL = True
    ADAPTER_OUTPUT_POLICY = (
        "Panaroo writes gene_presence_absence.Rtab; BioNodulo copies it to "
        "presence_matrix.tsv and its pangenome_gene_plot adapter derives "
        "pan_genome_plot.svg. The SVG is not a Panaroo artifact."
    )

    _CLEAN_MODES = {"strict", "moderate", "sensitive"}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if not _split_path_list(inputs.get("annotations")):
            return "At least one GFF annotation is required"
        clean_mode = str(inputs.get("clean_mode", "strict") or "strict")
        if clean_mode not in cls._CLEAN_MODES:
            return f"Unsupported Panaroo clean mode: {clean_mode}"
        validation = _positive_int(inputs.get("threads", 4), "threads", 4)
        if isinstance(validation, str):
            return validation
        try:
            core_threshold = float(inputs.get("core_threshold", 0.95))
        except (TypeError, ValueError):
            return "Core threshold must be a number"
        if not 0 <= core_threshold <= 1:
            return "Core threshold must be between 0 and 1"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        presence_matrix = out_dir / "presence_matrix.tsv"
        pan_genome_plot = out_dir / "pan_genome_plot.svg"
        annotations = _split_path_list(inputs.get("annotations"))
        threads = int(inputs.get("threads", 4) or 4)
        core_threshold = float(inputs.get("core_threshold", 0.95))

        cmd = [
            "panaroo",
            "-i",
            *annotations,
            "-o",
            str(out_dir),
            "--clean-mode",
            str(inputs.get("clean_mode", "strict") or "strict"),
        ]
        cmd.extend(["-t", str(threads)])
        cmd.extend(["--core_threshold", str(core_threshold)])
        if inputs.get("remove_invalid_genes"):
            cmd.append("--remove-invalid-genes")
        if inputs.get("merge_paralogs"):
            cmd.append("--merge_paralogs")

        cmd.extend([
            "&&",
            "cp",
            str(out_dir / "gene_presence_absence.Rtab"),
            str(presence_matrix),
            "&&",
            "python",
            "-m",
            "bionodulo.nodes.scripts.pangenome_gene_plot",
            "--input",
            str(presence_matrix),
            "--output",
            str(pan_genome_plot),
            "&&",
            "test",
            "-s",
            str(presence_matrix),
            "&&",
            "test",
            "-s",
            str(pan_genome_plot),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "presence_matrix.tsv", node_out / "pan_genome_plot.svg"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "annotations": (
                    "GFF",
                    {"multiple": True, "description": "One or more Prokka-style GFF3 annotation files"},
                ),
            },
            "optional": {
                "clean_mode": ("STRING", {"default": "strict", "options": ["strict", "moderate", "sensitive"]}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
                "core_threshold": ("FLOAT", {"default": 0.95, "min": 0.0, "max": 1.0, "step": 0.01}),
                "remove_invalid_genes": ("BOOLEAN", {"default": False}),
                "merge_paralogs": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
