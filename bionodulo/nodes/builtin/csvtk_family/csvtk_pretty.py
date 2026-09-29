"""``csvtk pretty``: convert CSV to a readable aligned table.

Generated from the tool's own --help output in the pinned csvtk v0.31.0 image.
Help page SHA-256: c314b7d292b84ef2da7acbe4e1b6dd5074ceedc9021b25c54a59814bfc853aed

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import CsvtkBase


class CsvtkPrettyNode(CsvtkBase):
    """convert CSV to a readable aligned table"""

    NODE_ID = 'csvtk_pretty'
    DISPLAY_NAME = 'csvtk pretty'
    SUBCOMMAND = 'pretty'
    DESCRIPTION = 'convert CSV to a readable aligned table'
    SEARCH_ALIASES = ['csvtk', 'pretty']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('csvtk_pretty.out',)
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
                "align_center": ('STRING', {'description': 'align right for selected columns (field index/range or column name, type "csvtk pretty -h" for examples)', 'default': ''}),
                "align_right": ('STRING', {'description': 'align right for selected columns (field index/range or column name, type "csvtk pretty -h" for examples)', 'default': ''}),
                "buf_rows": ('INT', {'description': 'the number of rows to determine the min and max widths (0 for all rows) (default 1024)', 'default': ''}),
                "clip": ('BOOLEAN', {'description': 'clip longer cell instead of wrapping', 'default': False}),
                "clip_mark": ('STRING', {'description': 'clip mark', 'default': '...'}),
                "max_width": ('INT', {'description': 'max width', 'default': ''}),
                "min_width": ('INT', {'description': 'min width', 'default': ''}),
                "separator": ('STRING', {'description': 'fields/columns separator', 'default': '   '}),
                "style": ('STRING', {'description': 'output syle. available vaules: default, plain, simple, 3line, grid, light, bold, double. check https://github.com/shenwei356/stable', 'default': ''}),
                "wrap_delimiter": ('STRING', {'description': 'delimiter for wrapping cells', 'default': ' '}),
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
