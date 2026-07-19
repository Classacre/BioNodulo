"""Compatibility composite for the historical two-image ODGI node."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from .odgi_adapter import ODGICommandNode, bash_pipeline, validate_input_file, validate_positive_int


class ODGIVisualizeNode(ODGICommandNode):
    """Build, sort, lay out, and render the historical 1D/2D image pair."""

    NODE_ID = "odgi_visualize"
    DISPLAY_NAME = "odgi Visualize"
    DESCRIPTION = "Compatibility composite: ODGI build, viz, sort, layout, and draw"
    SEARCH_ALIASES = ["odgi", "visualize", "pangenome", "graph viz", "graph layout"]
    RETURN_TYPES = ("IMAGE", "IMAGE")
    RETURN_NAMES = ("graph_1d", "graph_2d")
    UPSTREAM_SOURCE = "src/subcommand/{build,viz,sort,layout,draw}_main.cpp"
    COMPATIBILITY_COMPOSITE = True
    COMPATIBILITY_OPERATIONS = ("odgi_build", "odgi_viz", "odgi_sort", "odgi_layout", "odgi_draw")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gfa_graph": ("GFA", {"description": "Readable GFAv1 graph"}),
            },
            "optional": {
                "width": ("INT", {"default": 1500, "min": 1}),
                "height": ("INT", {"default": 500, "min": 1}),
                "draw_height": ("INT", {"default": 1000, "min": 1}),
                "show_path_names": ("BOOLEAN", {"default": True}),
                "color_paths": ("BOOLEAN", {"default": True}),
                "threads": ("INT", {"default": 1, "min": 1}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "graph_1d.png", node_out / "graph_2d.png"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        error = validate_input_file(inputs.get("gfa_graph"), "gfa_graph")
        if error:
            return error
        for name in ("width", "height", "draw_height", "threads"):
            error = validate_positive_int(inputs.get(name, 1), name)
            if error:
                return error
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        graph = output / "graph.og"
        sorted_graph = output / "sorted.og"
        layout = output / "graph.lay"
        image_1d = output / "graph_1d.png"
        image_2d = output / "graph_2d.png"
        threads = str(inputs.get("threads", 1))

        build = ["odgi", "build", "-g", str(inputs.get("gfa_graph", "")), "-o", str(graph), "-O", "-t", threads]
        viz = ["odgi", "viz", "-i", str(graph), "-o", str(image_1d), "-x", str(inputs.get("width", 1500)), "-y", str(inputs.get("height", 500))]
        if not inputs.get("show_path_names", True):
            viz.append("-H")
        viz.extend(["-t", threads])
        sort = ["odgi", "sort", "-i", str(graph), "-o", str(sorted_graph), "-p", "Ygs", "-O", "-t", threads]
        layout_command = ["odgi", "layout", "-i", str(sorted_graph), "-o", str(layout), "-t", threads]
        draw = ["odgi", "draw", "-i", str(sorted_graph), "-c", str(layout), "-p", str(image_2d), "-H", str(inputs.get("draw_height", 1000))]
        if inputs.get("color_paths", True):
            draw.append("-C")
        draw.extend(["-t", threads])
        return bash_pipeline([shlex.join(command) for command in (build, viz, sort, layout_command, draw)])
