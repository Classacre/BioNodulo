"""deepTools plotProfile node pinned to 3.5.6."""

from __future__ import annotations

from typing import Any

from .adapter import DeepToolsCommandNode, deeptools_source_urls


class DeepToolsPlotProfileNode(DeepToolsCommandNode):
    """Render an average signal profile from a computeMatrix artifact."""

    NODE_ID = "deeptools_plot_profile"
    DISPLAY_NAME = "deepTools Plot Profile"
    DESCRIPTION = "Plot average signal profiles from a deepTools computeMatrix artifact"
    SEARCH_ALIASES = ["deeptools", "plotprofile", "profile plot", "average profile", "signal profile"]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("profile",)
    REQUIRED_EXECUTABLES = ["plotProfile"]
    OUTPUT_FILENAMES = ("profile.png",)
    DOCUMENTATION_URL = "https://deeptools.readthedocs.io/en/3.5.6/content/tools/plotProfile.html"
    SOURCE_PATHS = (
        "deeptools/plotProfile.py",
        "deeptools/parserCommon.py",
        "deeptools/heatmapper.py",
        "docs/content/tools/plotProfile.rst",
        "pyproject.toml",
    )
    SOURCE_URLS = deeptools_source_urls(*SOURCE_PATHS)
    SOURCE_URL = SOURCE_URLS[0]
    UPSTREAM_SOURCE = "; ".join(SOURCE_PATHS[:3])

    PLOT_TYPES = ("lines", "fill", "se", "std", "overlapped_lines", "heatmap")
    LEGEND_LOCATIONS = (
        "best",
        "upper-right",
        "upper-left",
        "upper-center",
        "lower-left",
        "lower-right",
        "lower-center",
        "center",
        "center-left",
        "center-right",
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "matrix": ("FILE", {"description": "Matrix from computeMatrix"}),
            },
            "optional": {
                "plot_title": ("STRING", {"default": ""}),
                "plot_type": ("STRING", {"default": "lines", "options": list(cls.PLOT_TYPES)}),
                "plot_height": ("FLOAT", {"default": 7.0, "min": 0.5, "max": 100.0}),
                "plot_width": ("FLOAT", {"default": 11.0, "min": 1.0}),
                "per_group": ("BOOLEAN", {"default": False}),
                "colors": (
                    "STRING",
                    {"default": [], "multiple": True, "description": "Matplotlib colors"},
                ),
                "samples_label": (
                    "STRING",
                    {"default": [], "multiple": True, "description": "Sample labels"},
                ),
                "regions_label": (
                    "STRING",
                    {"default": [], "multiple": True, "description": "Region labels"},
                ),
                "y_axis_label": ("STRING", {"default": ""}),
                "start_label": ("STRING", {"default": ""}),
                "end_label": ("STRING", {"default": ""}),
                "legend_location": (
                    "STRING",
                    {"default": "best", "options": list(cls.LEGEND_LOCATIONS)},
                ),
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
        plot_type = str(inputs.get("plot_type", "lines"))
        if plot_type not in cls.PLOT_TYPES:
            return f"Unsupported plotProfile plot type: {plot_type}"
        legend = str(inputs.get("legend_location", "best"))
        if legend not in cls.LEGEND_LOCATIONS:
            return f"Unsupported plotProfile legend location: {legend}"
        height = inputs.get("plot_height", 7.0)
        width = inputs.get("plot_width", 11.0)
        if isinstance(height, bool) or not isinstance(height, (int, float)) or not 0.5 <= float(height) <= 100:
            return "plot_height must be between 0.5 and 100"
        if isinstance(width, bool) or not isinstance(width, (int, float)) or float(width) < 1:
            return "plot_width must be at least 1"
        for key in ("colors", "samples_label", "regions_label"):
            try:
                cls.split_cli_values(inputs.get(key))
            except ValueError as exc:
                return f"{key} is not a valid argument list: {exc}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        command = [
            "plotProfile",
            "-m",
            str(inputs.get("matrix", "")),
            "--outFileName",
            str(cls.output_dir(inputs) / cls.OUTPUT_FILENAMES[0]),
            "--plotType",
            str(inputs.get("plot_type", "lines")),
            "--plotHeight",
            str(inputs.get("plot_height", 7.0)),
            "--plotWidth",
            str(inputs.get("plot_width", 11.0)),
        ]
        if inputs.get("per_group"):
            command.append("--perGroup")
        for key, flag in (
            ("colors", "--colors"),
            ("samples_label", "--samplesLabel"),
            ("regions_label", "--regionsLabel"),
        ):
            values = cls.split_cli_values(inputs.get(key))
            if values:
                command.append(flag)
                command.extend(values)
        for key, flag in (
            ("plot_title", "--plotTitle"),
            ("y_axis_label", "--yAxisLabel"),
            ("start_label", "--startLabel"),
            ("end_label", "--endLabel"),
        ):
            if inputs.get(key):
                command.extend([flag, str(inputs[key])])
        command.extend(["--legendLocation", str(inputs.get("legend_location", "best"))])
        return command
