"""``csvtk splitxlsx``: split XLSX sheet into multiple sheets according to column values.

Generated from the tool's own --help output in the pinned csvtk v0.31.0 image.
Help page SHA-256: 97c045cf3a463a65200a796bb8d29486010f4416c25d884ef526411e8effcaf2

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import CsvtkBase


class CsvtkSplitxlsxNode(CsvtkBase):
    """split XLSX sheet into multiple sheets according to column values"""

    NODE_ID = 'csvtk_splitxlsx'
    DISPLAY_NAME = 'csvtk splitxlsx'
    SUBCOMMAND = 'splitxlsx'
    DESCRIPTION = 'split XLSX sheet into multiple sheets according to column values'
    SEARCH_ALIASES = ['csvtk', 'splitxlsx']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('csvtk_splitxlsx.out',)
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
                "fields": ('STRING', {'description': 'comma separated key fields, column name or index. e.g. -f 1-3 or -f id,id2 or -F -f "group*" (default "1")', 'default': ''}),
                "fuzzy_fields": ('BOOLEAN', {'description': 'using fuzzy fields, e.g., -F -f "*name" or -F -f "id123*"', 'default': False}),
                "ignore_case": ('BOOLEAN', {'description': 'ignore case (cell value)', 'default': False}),
                "list_sheets": ('BOOLEAN', {'description': 'list all sheets', 'default': False}),
                "sheet_index": ('INT', {'description': 'Nth sheet to retrieve', 'default': 1}),
                "sheet_name": ('STRING', {'description': 'sheet to retrieve', 'default': ''}),
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
