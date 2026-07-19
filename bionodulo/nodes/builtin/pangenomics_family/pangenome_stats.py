"""Stable owner for ``pangenome_stats``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import _non_negative_int, _path_value
from .evidence import PangenomicsCommandContract


class PangenomeStatsNode(PangenomicsCommandContract):
    """Compute graph growth statistics with Panacus histgrowth."""

    NODE_ID = "pangenome_stats"
    DISPLAY_NAME = "Pangenome Stats"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Compute pangenome graph growth curves and a deterministic threshold summary with Panacus."
    SEARCH_ALIASES = ["pangenome", "panacus", "core graph", "growth curve", "coverage", "rarefaction"]
    RETURN_TYPES = ("JSON", "FILE")
    RETURN_NAMES = ("stats", "rarefaction")
    REQUIRED_EXECUTABLES = ["panacus"]
    REQUIRED_CONDA_PACKAGES = ["panacus"]
    DOCUMENTATION_URL = "https://github.com/marschall-lab/panacus"
    VERSION = "0.3.3"
    SHELL = True
    ADAPTER_OUTPUT_POLICY = (
        "Panacus writes rarefaction.tsv; BioNodulo's pangenome_stats_summary adapter "
        "derives stats.json from that table. stats.json is not a Panacus artifact."
    )

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if not _path_value(inputs.get("graph")):
            return "graph must be a non-empty path-like value"
        try:
            core_threshold = float(inputs.get("core_threshold", 0.9))
            shell_threshold = float(inputs.get("shell_threshold", 0.1))
        except (TypeError, ValueError):
            return "Pangenome thresholds must be numbers"
        if not 0 <= shell_threshold <= 1 or not 0 <= core_threshold <= 1:
            return "Pangenome thresholds must be between 0 and 1"
        if core_threshold <= shell_threshold:
            return "Core threshold must be greater than shell threshold"
        count = str(inputs.get("count", "node") or "node")
        if count not in {"node", "edge", "bp", "all"}:
            return "count must be one of: all, bp, edge, node"
        validation = _non_negative_int(inputs.get("threads", 0), "threads")
        if isinstance(validation, str):
            return validation
        grouping_modes = sum(
            bool(value)
            for value in (
                inputs.get("groupby"),
                inputs.get("groupby_sample", False),
                inputs.get("groupby_haplotype", False),
            )
        )
        if grouping_modes > 1:
            return "groupby, groupby_sample, and groupby_haplotype are mutually exclusive"
        for name, minimum, maximum in (("coverage", 1.0, None), ("quorum", 0.0, 1.0)):
            values = str(inputs.get(name, "1" if name == "coverage" else "0") or "").split(",")
            try:
                numbers = [float(value) for value in values]
            except ValueError:
                return f"{name} must be a comma-separated numeric list"
            if not numbers or any(value < minimum for value in numbers):
                return f"{name} values must be at least {minimum:g}"
            if maximum is not None and any(value > maximum for value in numbers):
                return f"{name} values must be at most {maximum:g}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        rarefaction = out_dir / "rarefaction.tsv"
        stats = out_dir / "stats.json"
        threads = int(inputs.get("threads", 0) or 0)

        cmd = [
            "panacus",
            "histgrowth",
            str(inputs.get("graph", "")),
            "--count",
            str(inputs.get("count", "node") or "node"),
            "--coverage",
            str(inputs.get("coverage", "1") or "1"),
            "--quorum",
            str(inputs.get("quorum", "0") or "0"),
        ]
        if inputs.get("groupby"):
            cmd.extend(["--groupby", str(inputs["groupby"])])
        elif inputs.get("groupby_sample"):
            cmd.append("--groupby-sample")
        elif inputs.get("groupby_haplotype"):
            cmd.append("--groupby-haplotype")
        if inputs.get("include_hist"):
            cmd.append("--hist")
        if threads > 0:
            cmd.extend(["-t", str(threads)])

        cmd.extend([
            ">",
            str(rarefaction),
            "&&",
            "python",
            "-m",
            "bionodulo.nodes.scripts.pangenome_stats_summary",
            "--input",
            str(rarefaction),
            "--output",
            str(stats),
            "--core-threshold",
            str(float(inputs.get("core_threshold", 0.9) or 0.9)),
            "--shell-threshold",
            str(float(inputs.get("shell_threshold", 0.1) or 0.1)),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "stats.json", node_out / "rarefaction.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "graph": ("GFA", {"description": "Input pangenome graph in GFA format"}),
            },
            "optional": {
                "core_threshold": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.01}),
                "shell_threshold": ("FLOAT", {"default": 0.1, "min": 0.0, "max": 1.0, "step": 0.01}),
                "count": ("STRING", {"default": "node", "options": ["node", "edge", "bp", "all"]}),
                "coverage": ("STRING", {"default": "1", "description": "Comma-separated static coverage thresholds"}),
                "quorum": ("STRING", {"default": "0", "description": "Comma-separated quorum fractions"}),
                "groupby": ("FILE", {"description": "Optional Panacus group-by or path grouping file"}),
                "groupby_sample": ("BOOLEAN", {"default": False}),
                "groupby_haplotype": ("BOOLEAN", {"default": False}),
                "threads": ("INT", {"default": 0, "min": 0, "max": 64, "display": "slider"}),
                "include_hist": ("BOOLEAN", {"default": False, "description": "Include histogram rows in Panacus output"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
