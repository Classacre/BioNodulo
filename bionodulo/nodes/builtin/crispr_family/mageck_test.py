"""MAGeCK 0.5.9.5 treatment-versus-control ranking contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    MageckCommandNode,
    path_value,
    require_materialized_file,
    validate_choice,
    validate_output_prefix,
)


class MAGeCKTestNode(MageckCommandNode):
    """Rank genes and sgRNAs from a MAGeCK count table."""

    NODE_ID = "mageck_test"
    DISPLAY_NAME = "MAGeCK Test"
    DESCRIPTION = "Identify enriched or depleted genes from treatment and control CRISPR screen samples."
    SEARCH_ALIASES = ["BioNodulo builtin", "MAGeCK", "test", "essential genes", "gene ranking", "pooled screen"]
    RETURN_TYPES = ("TSV", "TSV")
    RETURN_NAMES = ("gene_summary", "sgrna_summary")
    REQUIRED_EXECUTABLES = ["mageck", "RRA"]
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
                "treatment_labels": (
                    "STRING",
                    {
                        "multiple": True,
                        "description": "One or more comparison groups of comma-separated treatment labels or indices",
                    },
                ),
            },
            "optional": {
                "output_prefix": ("STRING", {"default": "sample1"}),
                "control_labels": (
                    "STRING",
                    {
                        "multiple": True,
                        "description": (
                            "Optional comparison groups of control labels or indices; "
                            "defaults to all non-treatment samples"
                        ),
                    },
                ),
                "norm_method": ("STRING", {"default": "median", "options": list(cls.NORM_METHODS)}),
                "adjust_method": ("STRING", {"default": "fdr", "options": list(cls.ADJUST_METHODS)}),
                "sort_criteria": ("STRING", {"default": "neg", "options": list(cls.SORT_CRITERIA)}),
                "control_sgrna": (
                    "FILE",
                    {"description": "Control sgRNA IDs for normalization and the RRA null distribution"},
                ),
                "control_gene": (
                    "FILE",
                    {"description": "Genes whose sgRNAs define normalization and the RRA null distribution"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        prefix = str(inputs.get("output_prefix", "sample1"))
        return [node_dir / f"{prefix}.gene_summary.txt", node_dir / f"{prefix}.sgrna_summary.txt"]

    @staticmethod
    def _comparison_groups(value: Any) -> list[str]:
        if value in (None, ""):
            return []
        if isinstance(value, (list, tuple)):
            return [str(group) for group in value]
        return [str(value)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        treatments = cls._comparison_groups(inputs.get("treatment_labels"))
        controls = cls._comparison_groups(inputs.get("control_labels"))
        for key, groups, required in (
            ("treatment_labels", treatments, True),
            ("control_labels", controls, False),
        ):
            if required and not groups:
                return f"Input '{key}' must contain one or more comma-separated labels or indices"
            if any(not group or any(not label for label in group.split(",")) for group in groups):
                return f"Input '{key}' must contain non-empty comma-separated labels or indices"
        if controls and len(controls) != len(treatments):
            return "Input 'control_labels' must provide one group per treatment_labels group"
        validation = validate_output_prefix(inputs.get("output_prefix", "sample1"))
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
        control_sgrna = path_value(inputs.get("control_sgrna"))
        control_gene = path_value(inputs.get("control_gene"))
        if control_sgrna and control_gene:
            return "Inputs 'control_sgrna' and 'control_gene' are mutually exclusive"
        if inputs.get("norm_method", "median") == "control" and not (control_sgrna or control_gene):
            return "Input 'norm_method=control' requires control_sgrna or control_gene"
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        require_materialized_file(inputs.get("count_table"), "count_table")
        for key in ("control_sgrna", "control_gene"):
            if path_value(inputs.get(key)):
                require_materialized_file(inputs.get(key), key)
        if len(outputs) != len(cls.RETURN_TYPES):
            raise ValueError("mageck_test requires gene- and sgRNA-summary outputs")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        prefix = str(inputs.get("output_prefix", "sample1"))
        command = cls.checked_command(
            inputs,
            "mageck",
            "test",
            "-k",
            path_value(inputs.get("count_table")),
        )
        for group in cls._comparison_groups(inputs.get("treatment_labels")):
            command.extend(["-t", group])
        for group in cls._comparison_groups(inputs.get("control_labels")):
            command.extend(["-c", group])
        command.extend(["-n", str(output_dir / prefix)])
        for key, flag in (("control_sgrna", "--control-sgrna"), ("control_gene", "--control-gene")):
            if path_value(inputs.get(key)):
                command.extend([flag, path_value(inputs[key])])
        for key, flag in (
            ("norm_method", "--norm-method"),
            ("adjust_method", "--adjust-method"),
            ("sort_criteria", "--sort-criteria"),
        ):
            if inputs.get(key) not in (None, ""):
                command.extend([flag, str(inputs[key])])
        return command
