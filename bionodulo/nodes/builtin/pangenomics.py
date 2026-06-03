"""Pangenomics workflow nodes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


class ODGIVisualizeNode(CommandNode):
    """Visualize pangenome graph layouts with odgi."""
    NODE_ID = "odgi_visualize"
    DISPLAY_NAME = "odgi Visualize"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Visualize pangenome graphs in 1D and 2D layout using odgi."
    SEARCH_ALIASES = ["odgi", "visualize", "pangenome", "graph viz", "graph layout"]
    RETURN_TYPES = ("IMAGE", "IMAGE")
    RETURN_NAMES = ("graph_1d", "graph_2d")
    REQUIRED_EXECUTABLES = ["odgi"]
    REQUIRED_CONDA_PACKAGES = ["odgi"]
    DOCUMENTATION_URL = "https://odgi.readthedocs.io/"
    VERSION = "0.9.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        graph = out_dir / "graph.og"
        sorted_graph = out_dir / "sorted.og"
        graph_1d = out_dir / "graph_1d.png"
        graph_2d = out_dir / "graph_2d.png"

        cmd = [
            "odgi",
            "build",
            "-g",
            str(inputs.get("gfa_graph", "")),
            "-o",
            str(graph),
            "&&",
            "odgi",
            "viz",
            "-i",
            str(graph),
            "-o",
            str(graph_1d),
            "-x",
            str(inputs.get("width", 1200)),
            "-y",
            str(inputs.get("height", 200)),
        ]
        if inputs.get("show_path_names"):
            cmd.append("-p")
        cmd.extend([
            "&&",
            "odgi",
            "sort",
            "-i",
            str(graph),
            "-o",
            str(sorted_graph),
            "-Y",
            "&&",
            "odgi",
            "draw",
            "-i",
            str(sorted_graph),
            "-c",
            str(graph_2d),
            "-H",
            str(inputs.get("draw_height", 600)),
            "-C",
            str(inputs.get("draw_width", 1200)),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "graph_1d.png", node_out / "graph_2d.png"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gfa_graph": ("GFA", {"description": "Input pangenome graph in GFA format"}),
            },
            "optional": {
                "width": ("INT", {"default": 1200, "min": 100, "max": 10000}),
                "height": ("INT", {"default": 200, "min": 50, "max": 5000}),
                "draw_width": ("INT", {"default": 1200, "min": 100, "max": 10000}),
                "draw_height": ("INT", {"default": 600, "min": 50, "max": 5000}),
                "show_path_names": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
