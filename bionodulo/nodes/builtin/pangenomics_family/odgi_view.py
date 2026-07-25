"""Project an ODGI graph to GFAv1 with ``odgi view``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .odgi_adapter import ODGICommandNode, validate_input_file, validate_positive_int


class ODGIViewNode(ODGICommandNode):
    """Run ODGI's graph projection operation, capturing GFA from stdout."""

    NODE_ID = "odgi_view"
    DISPLAY_NAME = "ODGI View"
    DESCRIPTION = "Project an ODGI graph to GFAv1"
    SEARCH_ALIASES = ["odgi", "odgi view", "pangenome graph", "graph projection", "gfa"]
    RETURN_TYPES = ("GFA",)
    RETURN_NAMES = ("gfa_graph",)
    STDOUT_OUTPUT_INDEX = 0
    UPSTREAM_SOURCE = "src/subcommand/view_main.cpp"
    PREVIOUS_VERSIONS = ["0.9.0"]
    MIGRATIONS = [
        {
            "from_version": "0.9.0",
            "to_version": "0.9.2",
            "description": (
                "odgi_view now maps to the upstream view subcommand and emits GFA; "
                "use odgi_viz for legacy PNG visualization."
            ),
        }
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "graph": ("ODGI", {"description": "Readable ODGI graph"}),
            },
            "optional": {
                "threads": ("INT", {"default": 1, "min": 1}),
                "node_annotations": (
                    "BOOLEAN",
                    {"default": False, "description": "Emit ODGI node annotations in GFA output (-a)"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "graph.gfa"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        legacy_controls = sorted(
            name
            for name in ("mode", "width", "height", "show_path_names")
            if name in inputs
        )
        if legacy_controls:
            return (
                "legacy odgi_view visualization inputs are not accepted by the focused "
                f"view contract ({', '.join(legacy_controls)}); use odgi_viz"
            )
        error = validate_input_file(inputs.get("graph"), "graph")
        if error:
            return error
        error = validate_positive_int(inputs.get("threads", 1), "threads")
        if error:
            return error
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ["odgi", "view", "-i", str(inputs.get("graph", "")), "-g"]
        if inputs.get("node_annotations", False):
            command.append("-a")
        command.extend(["-t", str(inputs.get("threads", 1))])
        return command
