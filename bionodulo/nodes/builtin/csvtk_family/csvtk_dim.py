"""``csvtk dim``: dimensions of CSV file.

Generated from the tool's own --help output in the pinned csvtk v0.31.0 image.
Help page SHA-256: afe8ff98c3fb75ee796dc2e2b8e0260e66d4068b1a5c93919188ba3888b8a507

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import CsvtkBase


class CsvtkDimNode(CsvtkBase):
    """dimensions of CSV file"""

    NODE_ID = 'csvtk_dim'
    DISPLAY_NAME = 'csvtk dim'
    SUBCOMMAND = 'dim'
    DESCRIPTION = 'dimensions of CSV file'
    SEARCH_ALIASES = ['csvtk', 'dim']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('csvtk_dim.out',)
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
                "cols": ('BOOLEAN', {'description': 'only print number of columns (or using "csvtk ncol"', 'default': False}),
                "no_files": ('BOOLEAN', {'description': 'do not print file names (only affect --cols and --rows)', 'default': False}),
                "rows": ('BOOLEAN', {'description': 'only print number of rows (or using "csvtk nrow")', 'default': False}),
                "tabular": ('BOOLEAN', {'description': 'output in machine-friendly tabular format', 'default': False}),
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
