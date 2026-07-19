"""MAGeCK 0.5.9.5 treatment-versus-control ranking contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import MageckCommandNode, path_value, validate_choice, validate_output_prefix


class MAGeCKTestNode(MageckCommandNode):
    """Rank genes and sgRNAs from a MAGeCK count table."""

    NODE_ID = "mageck_test"
    DISPLAY_NAME = "MAGeCK Test"
    DESCRIPTION = "Identify enriched or depleted genes from treatment and control CRISPR screen samples."
    SEARCH_ALIASES = ["BioNodulo builtin", "MAGeCK", "test", "essential genes", "gene ranking", "pooled screen"]
    RETURN_TYPES = ("TSV", "TSV")
    RETURN_NAMES = ("gene_summary", "sgrna_summary")
    REQUIRED_PATH_INPUTS = ("count_table",)
    UPSTREAM_SOURCE = "mageck/argsParser.py:arg_test; mageck/crisprFunction.py:magecktest_main"
    NORM_METHODS = ("none", "median", "total", "control")
    ADJUST_METHODS = ("fdr", "holm", "pounds")
    SORT_CRITERIA = ("neg", "pos")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "count_table": ("TSV", {"description": "MAGeCK count table"}),
                "treatment_labels": ("STRING", {"description": "Comma-separated treatment labels or indices"}),
                "control_labels": ("STRING", {"description": "Comma-separated control labels or indices"}),
                "output_prefix": ("STRING", {"default": "mageck_test"}),
            },
            "optional": {
                "norm_method": ("STRING", {"default": "median", "options": list(cls.NORM_METHODS)}),
                "adjust_method": ("STRING", {"default": "fdr", "options": list(cls.ADJUST_METHODS)}),
                "sort_criteria": ("STRING", {"default": "neg", "options": list(cls.SORT_CRITERIA)}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        prefix = str(inputs.get("output_prefix", "mageck_test"))
        return [node_dir / f"{prefix}.gene_summary.txt", node_dir / f"{prefix}.sgrna_summary.txt"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("treatment_labels", "control_labels"):
            labels = str(inputs.get(key, "") or "").split(",")
            if not labels or any(not label for label in labels):
                return f"Input '{key}' must contain one or more comma-separated labels or indices"
        validation = validate_output_prefix(inputs.get("output_prefix", "mageck_test"))
        if validation is not True:
            return validation
        for key, default, choices in (
            ("norm_method", "median", cls.NORM_METHODS),
            ("adjust_method", "fdr", cls.ADJUST_METHODS),
            ("sort_criteria", "neg", cls.SORT_CRITERIA),
        ):
            value = inputs.get(key, default)
            if value in (None, ""):
                continue
            validation = validate_choice(value, key, choices)
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        prefix = str(inputs.get("output_prefix", "mageck_test"))
        command = cls.checked_command(
            inputs,
            "mageck",
            "test",
            "-k",
            path_value(inputs.get("count_table")),
            "-t",
            str(inputs.get("treatment_labels", "")),
            "-c",
            str(inputs.get("control_labels", "")),
            "-n",
            str(output_dir / prefix),
        )
        for key, flag in (
            ("norm_method", "--norm-method"),
            ("adjust_method", "--adjust-method"),
            ("sort_criteria", "--sort-criteria"),
        ):
            if inputs.get(key) not in (None, ""):
                command.extend([flag, str(inputs[key])])
        return command
