"""``csvtk sort``: sort by selected fields.

Generated from the tool's own --help output in the pinned csvtk v0.31.0 image.
Help page SHA-256: 6e6ff00327c891dbff5f15f1d302456fcfd1b9abe6d1b6947c869b7b8a1cd2d9

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import CsvtkBase


class CsvtkSortNode(CsvtkBase):
    """sort by selected fields"""

    NODE_ID = 'csvtk_sort'
    DISPLAY_NAME = 'csvtk sort'
    SUBCOMMAND = 'sort'
    DESCRIPTION = 'sort by selected fields'
    SEARCH_ALIASES = ['csvtk', 'sort']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('csvtk_sort.out',)
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
                "ignore_case": ('BOOLEAN', {'description': 'ignore-case', 'default': False}),
                "keys": ('STRING', {'description': 'keys (multiple values supported). sort type supported, "N" for natural order, "n" for number, "u" for user-defined order and "r" for reverse. e.g., "-k 1" or "-k A:r" or ""-k 1:nr -k 2" (default [1])', 'default': ''}),
                "levels": ('STRING', {'description': 'user-defined level file (one level per line, multiple values supported). format: <field>:<level-file>.  e.g., "-k name:u -L name:level.txt"', 'default': ''}),
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
