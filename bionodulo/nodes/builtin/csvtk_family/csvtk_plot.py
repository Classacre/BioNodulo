"""``csvtk plot``: plot common figures.

Generated from the tool's own --help output in the pinned csvtk v0.31.0 image.
Help page SHA-256: 690e9b77c7c19ffbfd2ccc3ad8d487ddff695b56153c69d0f5a66d8bce3a63b8

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import CsvtkBase


class CsvtkPlotNode(CsvtkBase):
    """plot common figures"""

    NODE_ID = 'csvtk_plot'
    DISPLAY_NAME = 'csvtk plot'
    SUBCOMMAND = 'plot'
    DESCRIPTION = 'plot common figures'
    SEARCH_ALIASES = ['csvtk', 'plot']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('csvtk_plot.out',)
    DOCUMENTATION_URL = 'https://github.com/shenwei356/csvtk'
    REQUIRED_EXECUTABLES = ['csvtk']
    REQUIRED_CONDA_PACKAGES = ['csvtk']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'table': ("FILE", {"description": 'Input table file'}),

            },
            "optional": {
                "delimiter": (
                    "STRING",
                    {
                        "default": "tab",
                        "options": ["tab", "comma"],
                        "description": "Input delimiter",
                    },
                ),
                "axis_width": ('FLOAT', {'description': 'axis width', 'default': 1.5}),
                "data_field": ('STRING', {'description': 'column index or column name of data', 'default': '1'}),
                "format": ('STRING', {'description': 'image format for stdout when flag -o/--out-file not given. available values: eps, jpg|jpeg, pdf, png, svg, and tif|tiff. (default "png")', 'default': ''}),
                "group_field": ('STRING', {'description': 'column index or column name of group', 'default': ''}),
                "height": ('FLOAT', {'description': 'Figure height', 'default': 4.5}),
                "label_size": ('INT', {'description': 'label font size', 'default': 14}),
                "na_values": ('STRING', {'description': 'NA values, case ignored', 'default': '[,NA,N/A]'}),
                "scale": ('FLOAT', {'description': 'scale the image width/height, tick, axes, line/point and font sizes proportionally (default 1)', 'default': ''}),
                "skip_na": ('BOOLEAN', {'description': 'skip NA values in --na-values', 'default': False}),
                "tick_label_size": ('INT', {'description': 'tick label font size', 'default': 12}),
                "tick_width": ('FLOAT', {'description': 'axis tick width', 'default': 1.5}),
                "title": ('STRING', {'description': 'Figure title', 'default': ''}),
                "title_size": ('INT', {'description': 'title font size', 'default': 16}),
                "width": ('FLOAT', {'description': 'Figure width', 'default': 6.0}),
                "x_max": ('STRING', {'description': 'maximum value of X axis', 'default': ''}),
                "x_min": ('STRING', {'description': 'minimum value of X axis', 'default': ''}),
                "xlab": ('STRING', {'description': 'x label text', 'default': ''}),
                "y_max": ('STRING', {'description': 'maximum value of Y axis', 'default': ''}),
                "y_min": ('STRING', {'description': 'minimum value of Y axis', 'default': ''}),
                "ylab": ('STRING', {'description': 'y label text', 'default': ''}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = ['csvtk', cls.SUBCOMMAND]
        mode = str(inputs.get("delimiter", "tab") or "tab")
        if mode == "tab":
            command.append("--tabs")
        # Required flags must be rendered too. Iterating only "optional" silently
        # dropped every empirically-required flag (csvtk mutate --name and friends).
        declared_types = cls.INPUT_TYPES()
        for category in ("required", "optional"):
            for name, spec in declared_types.get(category, {}).items():
                if name in ('delimiter', 'table'):
                    continue
                value = inputs.get(name)
                if value in (None, ""):
                    continue
                declared = spec[0] if isinstance(spec, (list, tuple)) else spec
                default = spec[1].get("default") if isinstance(spec, tuple) and len(spec) > 1 else None
                token = getattr(cls, "FLAG_TOKENS", {}).get(name) or f"--{name.replace('_', '-')}"
                if declared == "BOOLEAN":
                    if bool(value):
                        command.append(token)
                    continue
                if value == default:
                    continue
                command.extend([token, str(value)])
        command.extend(['--out-file', str(output_dir / cls.OUTPUT_FILENAMES[0])])
        command.append(str(inputs.get('table', "")))
        return command
