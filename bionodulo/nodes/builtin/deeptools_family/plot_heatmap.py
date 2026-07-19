"""deepTools plotHeatmap node pinned to 3.5.6."""

from __future__ import annotations

from typing import Any

from .adapter import DeepToolsCommandNode


class DeepToolsPlotHeatmapNode(DeepToolsCommandNode):
    """Render one heatmap image from a computeMatrix artifact."""

    NODE_ID = "deeptools_plot_heatmap"
    DISPLAY_NAME = "deepTools Plot Heatmap"
    DESCRIPTION = "Publication-quality heatmaps from deepTools computeMatrix output"
    SEARCH_ALIASES = ["deeptools", "plotheatmap", "heatmap", "signal matrix"]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("heatmap",)
    REQUIRED_EXECUTABLES = ["plotHeatmap"]
    OUTPUT_FILENAMES = ("heatmap.png",)
    DOCUMENTATION_URL = "https://deeptools.readthedocs.io/en/3.5.6/content/tools/plotHeatmap.html"
    UPSTREAM_SOURCE = "deeptools/plotHeatmap.py"

    SORT_MODES = ("descend", "ascend", "no", "keep")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "matrix": ("FILE", {"description": "Matrix from computeMatrix"}),
            },
            "optional": {
                "heatmap_height": ("FLOAT", {"default": 28.0, "min": 3.0, "max": 100.0}),
                "heatmap_width": ("FLOAT", {"default": 4.0, "min": 1.0, "max": 100.0}),
                "colormap": ("STRING", {"default": "RdYlBu", "description": "Space-separated matplotlib color maps"}),
                "sort_regions": (
                    "STRING",
                    {"default": "descend", "options": list(cls.SORT_MODES)},
                ),
                "kmeans": ("INT", {"default": 0, "min": 0}),
                "plot_title": ("STRING", {"default": ""}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = cls.require_path(inputs, "matrix")
        if validation is not True:
            return validation
        height = inputs.get("heatmap_height", 28.0)
        width = inputs.get("heatmap_width", 4.0)
        if isinstance(height, bool) or not isinstance(height, (int, float)) or not 3 < float(height) <= 100:
            return "heatmap_height must be greater than 3 and at most 100"
        if isinstance(width, bool) or not isinstance(width, (int, float)) or not 1 <= float(width) <= 100:
            return "heatmap_width must be between 1 and 100"
        sort_regions = str(inputs.get("sort_regions", "descend"))
        if sort_regions not in cls.SORT_MODES:
            return f"Unsupported plotHeatmap sort mode: {sort_regions}"
        kmeans = inputs.get("kmeans", 0)
        if isinstance(kmeans, bool) or not isinstance(kmeans, int) or kmeans < 0:
            return "kmeans must be a non-negative integer"
        try:
            if not cls.split_cli_values(inputs.get("colormap", "RdYlBu")):
                return "colormap must contain at least one value"
        except ValueError as exc:
            return f"colormap is not a valid argument list: {exc}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        command = [
            "plotHeatmap",
            "-m",
            str(inputs.get("matrix", "")),
            "--outFileName",
            str(cls.output_dir(inputs) / cls.OUTPUT_FILENAMES[0]),
            "--heatmapHeight",
            str(inputs.get("heatmap_height", 28.0)),
            "--heatmapWidth",
            str(inputs.get("heatmap_width", 4.0)),
            "--colorMap",
            *cls.split_cli_values(inputs.get("colormap", "RdYlBu")),
            "--sortRegions",
            str(inputs.get("sort_regions", "descend")),
        ]
        if inputs.get("kmeans", 0) > 0:
            command.extend(["--kmeans", str(inputs["kmeans"])])
        if inputs.get("plot_title"):
            command.extend(["--plotTitle", str(inputs["plot_title"])])
        return command
