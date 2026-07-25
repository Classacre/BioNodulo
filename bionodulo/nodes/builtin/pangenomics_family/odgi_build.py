"""Build an ODGI graph from GFA and retain the legacy JSON summary port."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from .odgi_adapter import (
    ODGICommandNode,
    bash_pipeline,
    safe_output_stem,
    stats_json_pipeline,
    validate_input_file,
    validate_positive_int,
)


class ODGIBuildNode(ODGICommandNode):
    """Run ``odgi build`` and adapt its documented summary to JSON."""

    NODE_ID = "odgi_build"
    DISPLAY_NAME = "odgi Build"
    DESCRIPTION = "Build an optimized ODGI graph from GFA and emit deterministic summary JSON"
    SEARCH_ALIASES = ["odgi", "odgi build", "gfa to odgi", "pangenome graph", "graph conversion"]
    RETURN_TYPES = ("ODGI", "JSON")
    RETURN_NAMES = ("graph_odgi", "stats")
    REQUIRED_EXECUTABLES = ["odgi", "bash"]
    REQUIRED_CONDA_PACKAGES = ["odgi", "bash"]
    CONDA_PACKAGE_CONSTRAINTS = {"odgi": "0.9.2", "bash": "*"}
    PACKAGE_CONSTRAINTS = ("odgi==0.9.2", "bash")
    PACKAGE_CONSTRAINT = "; ".join(PACKAGE_CONSTRAINTS)
    UPSTREAM_SOURCE = "src/subcommand/build_main.cpp"
    SUMMARY_SOURCE = "src/subcommand/stats_main.cpp"
    VALIDATE_SOURCE = "src/subcommand/validate_main.cpp"
    SOURCE_URLS = (
        "https://github.com/pangenome/odgi/blob/be6a0202501d7ea2ac57f9ad89d4d10ed5dbd7c6/src/subcommand/build_main.cpp",
        "https://github.com/pangenome/odgi/blob/be6a0202501d7ea2ac57f9ad89d4d10ed5dbd7c6/src/subcommand/stats_main.cpp",
        "https://github.com/pangenome/odgi/blob/be6a0202501d7ea2ac57f9ad89d4d10ed5dbd7c6/src/subcommand/validate_main.cpp",
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gfa_graph": ("GFA", {"description": "Readable GFAv1 graph"}),
            },
            "optional": {
                "threads": ("INT", {"default": 1, "min": 1}),
                "compact_ids": (
                    "BOOLEAN",
                    {"default": False, "description": "Compact node identifiers with odgi build -O"},
                ),
                "validate": (
                    "BOOLEAN",
                    {"default": False, "description": "Run odgi validate after construction"},
                ),
                "output_name": ("STRING", {"default": "", "description": "Stable output filename stem"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _planned_paths(cls, inputs: dict[str, Any], node_out: str | Path) -> tuple[Path, Path]:
        fallback = Path(str(inputs.get("gfa_graph", "graph"))).name
        for suffix in (".gfa.gz", ".gfa", ".gz"):
            if fallback.lower().endswith(suffix):
                fallback = fallback[: -len(suffix)]
                break
        stem = safe_output_stem(inputs.get("output_name"), fallback or "graph")
        root = Path(node_out)
        return root / f"{stem}.odgi", root / f"{stem}.stats.json"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return list(cls._planned_paths(inputs, node_out))

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        error = validate_input_file(inputs.get("gfa_graph"), "gfa_graph")
        if error:
            return error
        error = validate_positive_int(inputs.get("threads", 1), "threads")
        if error:
            return error
        return True

    @classmethod
    def build_argv(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        graph_odgi, _stats = cls._planned_paths(inputs, output)
        command = [
            "odgi",
            "build",
            "-g",
            str(inputs.get("gfa_graph", "")),
            "-o",
            str(graph_odgi),
        ]
        if inputs.get("compact_ids", False):
            command.append("-O")
        command.extend(["-t", str(inputs.get("threads", 1))])
        return command

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        graph_odgi, stats = cls._planned_paths(inputs, output)
        threads = int(inputs.get("threads", 1))
        commands = [shlex.join(cls.build_argv(inputs))]
        if inputs.get("validate", False):
            commands.append(shlex.join(["odgi", "validate", "-i", str(graph_odgi), "-t", str(threads)]))
        commands.append(stats_json_pipeline(graph_odgi, stats, threads))
        return bash_pipeline(commands)
