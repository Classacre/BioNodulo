"""Focused CheckM 1.2.5 lineage workflow with explicit reference data."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin.metagenomics_family.adapter import (
    MetagenomicsCommandNode,
    add_flag,
    path_value,
    validate_int,
    validate_number,
)


class CheckMNode(MetagenomicsCommandNode):
    """Assess MAG completeness and contamination with CheckM lineage_wf."""

    NODE_ID = "checkm"
    DISPLAY_NAME = "CheckM"
    DESCRIPTION = "Run CheckM 1.2.5 lineage_wf with an explicit CheckM reference-data directory."
    SEARCH_ALIASES = ["BioNodulo builtin", "CheckM", "lineage_wf", "MAG quality", "completeness", "contamination"]
    RETURN_TYPES = ("DIRECTORY", "TSV")
    RETURN_NAMES = ("analysis_dir", "quality_report")
    REQUIRED_EXECUTABLES = ["checkm"]
    REQUIRED_CONDA_PACKAGES = ["checkm-genome"]
    VERSION = "1.2.5"
    BIOCONDA_VERSION = VERSION
    BIOCONDA_CONSTRAINT = "checkm-genome=1.2.5"
    GIT_URL = "https://github.com/Ecogenomics/CheckM.git"
    GIT_COMMIT = "acb42ba20b29661054933d0df44a78fd28fd0bcc"
    UPSTREAM_TAG = "v1.2.5"
    DOCUMENTATION_URL = "https://github.com/Ecogenomics/CheckM/tree/v1.2.5"
    UPSTREAM_SOURCE = "bin/checkm lineage_wf parser; checkm/main.py; checkm/checkmData.py"
    REFERENCE_DATA_SEMANTICS = (
        "checkm_data must contain a valid CheckM manifest and is supplied through CHECKM_DATA_PATH."
    )
    EXIT_SEMANTICS = (
        "CheckM non-zero exit is fatal; BioNodulo requires both the lineage_wf analysis directory and tabular QA report."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bins": ("DIRECTORY", {"description": "Directory containing genome bins"}),
                "checkm_data": ("DIRECTORY", {"description": "CheckM 1.2.5 reference-data root with manifest"}),
            },
            "optional": {
                "extension": ("STRING", {"default": "fna", "description": "Bin filename extension without dot"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 256}),
                "pplacer_threads": ("INT", {"default": 1, "min": 1, "max": 64}),
                "reduced_tree": ("BOOLEAN", {"default": False}),
                "keep_alignments": ("BOOLEAN", {"default": False}),
                "genes": ("BOOLEAN", {"default": False, "description": "Bins contain amino-acid genes"}),
                "force_domain": ("BOOLEAN", {"default": False}),
                "no_refinement": ("BOOLEAN", {"default": False}),
                "individual_markers": ("BOOLEAN", {"default": False}),
                "skip_adj_correction": ("BOOLEAN", {"default": False}),
                "skip_pseudogene_correction": ("BOOLEAN", {"default": False}),
                "aai_strain": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / "analysis", node_dir / "quality_report.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("bins", "checkm_data"):
            if not path_value(inputs.get(key)):
                return f"Input '{key}' must be a non-empty path-like value"
        extension = str(inputs.get("extension", "fna") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9]+", extension):
            return "Input 'extension' must contain only letters and digits, without a leading dot"
        validation = validate_int(inputs.get("threads", 1), "threads", minimum=1, maximum=256)
        if validation is not True:
            return validation
        validation = validate_int(inputs.get("pplacer_threads", 1), "pplacer_threads", minimum=1, maximum=64)
        if validation is not True:
            return validation
        return validate_number(inputs.get("aai_strain", 0.9), "aai_strain", minimum=0, maximum=1)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = [
            "env",
            f"CHECKM_DATA_PATH={path_value(inputs.get('checkm_data'))}",
            "checkm",
            "lineage_wf",
            "-x",
            str(inputs.get("extension", "fna")),
            "-t",
            str(inputs.get("threads", 1)),
            "--pplacer_threads",
            str(inputs.get("pplacer_threads", 1)),
            "--aai_strain",
            str(inputs.get("aai_strain", 0.9)),
        ]
        add_flag(command, "--reduced_tree", inputs.get("reduced_tree"))
        add_flag(command, "--ali", inputs.get("keep_alignments"))
        add_flag(command, "--genes", inputs.get("genes"))
        add_flag(command, "--force_domain", inputs.get("force_domain"))
        add_flag(command, "--no_refinement", inputs.get("no_refinement"))
        add_flag(command, "--individual_markers", inputs.get("individual_markers"))
        add_flag(command, "--skip_adj_correction", inputs.get("skip_adj_correction"))
        add_flag(command, "--skip_pseudogene_correction", inputs.get("skip_pseudogene_correction"))
        command.extend(
            [
                "--tab_table",
                "-f",
                str(output / "quality_report.tsv"),
                path_value(inputs.get("bins")),
                str(output / "analysis"),
            ]
        )
        return command
