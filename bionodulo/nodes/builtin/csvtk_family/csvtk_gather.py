"""``csvtk gather``: gather columns into key-value pairs, like tidyr::gather/pivot_longer.

Generated from the tool's own --help output in the pinned csvtk v0.31.0 image.
Help page SHA-256: ab61f5d8f4a7b910f3a0d517102d8e35b61f33a2041de81a0fb6cc8c22a17e01

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import CsvtkBase


class CsvtkGatherNode(CsvtkBase):
    """gather columns into key-value pairs, like tidyr::gather/pivot_longer"""

    NODE_ID = 'csvtk_gather'
    DISPLAY_NAME = 'csvtk gather'
    SUBCOMMAND = 'gather'
    DESCRIPTION = 'gather columns into key-value pairs, like tidyr::gather/pivot_longer'
    SEARCH_ALIASES = ['csvtk', 'gather']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('csvtk_gather.out',)
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
                "fields": ('STRING', {'description': 'fields for gathering. e.g -f 1,2 or -f columnA,columnB, or -f -columnA for unselect columnA', 'default': ''}),
                "fuzzy_fields": ('BOOLEAN', {'description': 'using fuzzy fields, e.g., -F -f "*name" or -F -f "id123*"', 'default': False}),
                "key": ('STRING', {'description': 'name of key column to create in output', 'default': ''}),
                "value": ('STRING', {'description': 'name of value column to create in output', 'default': ''}),
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
