"""Render one-dimensional ODGI graph visualizations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .odgi_adapter import ODGICommandNode, validate_input_file, validate_positive_int


class ODGIVizNode(ODGICommandNode):
    """Run the documented ``odgi viz`` operation."""

    NODE_ID = "odgi_viz"
    DISPLAY_NAME = "ODGI Viz"
    DESCRIPTION = "Render a pangenome graph as a one-dimensional PNG"
    SEARCH_ALIASES = ["odgi", "odgi viz", "graph visualization", "pangenome graph", "graph layout"]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("viz_image",)
    UPSTREAM_SOURCE = "src/subcommand/viz_main.cpp"
    SOURCE_URLS = (
        "https://github.com/pangenome/odgi/blob/be6a0202501d7ea2ac57f9ad89d4d10ed5dbd7c6/src/subcommand/viz_main.cpp",
    )

    _MODES = {"plain", "gradient"}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gfa_graph": (
                    "FILE",
                    {
                        "description": (
                            "Readable native ODGI graph (preferred) or GFAv1 graph; ODGI converts GFAv1 on the fly"
                        )
                    },
                ),
            },
            "optional": {
                "width": ("INT", {"default": 1500, "min": 1}),
                "height": ("INT", {"default": 500, "min": 1}),
                "show_paths": (
                    "BOOLEAN",
                    {"default": True, "description": "Show path names (ODGI shows them by default)"},
                ),
                "viz_mode": (
                    "STRING",
                    {
                        "default": "plain",
                        "options": ["plain", "gradient"],
                        "description": "Gradient maps to ODGI's documented -d darkness mode",
                    },
                ),
                "threads": ("INT", {"default": 1, "min": 1}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "viz_image.png"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        error = validate_input_file(inputs.get("gfa_graph"), "gfa_graph")
        if error:
            return error
        mode = str(inputs.get("viz_mode", "plain") or "plain")
        if mode not in cls._MODES:
            return f"Unsupported ODGI Viz mode: {mode}"
        for name in ("width", "height", "threads"):
            error = validate_positive_int(inputs.get(name, 1), name)
            if error:
                return error
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = [
            "odgi",
            "viz",
            "-i",
            str(inputs.get("gfa_graph", "")),
            "-o",
            str(output / "viz_image.png"),
            "-x",
            str(inputs.get("width", 1500)),
            "-y",
            str(inputs.get("height", 500)),
        ]
        if not inputs.get("show_paths", True):
            command.append("-H")
        if str(inputs.get("viz_mode", "plain") or "plain") == "gradient":
            command.append("-d")
        command.extend(["-t", str(inputs.get("threads", 1))])
        return command
