"""``csvtk mutate``: create new column from selected fields by regular expression.

Generated from the tool's own --help output in the pinned csvtk v0.31.0 image.
Help page SHA-256: a6251bf40ab326973aeb863b4e2ca6bae2c00cb6340b67ae936584048482d30d

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import CsvtkBase


class CsvtkMutateNode(CsvtkBase):
    """create new column from selected fields by regular expression"""

    NODE_ID = 'csvtk_mutate'
    DISPLAY_NAME = 'csvtk mutate'
    SUBCOMMAND = 'mutate'
    DESCRIPTION = 'create new column from selected fields by regular expression'
    SEARCH_ALIASES = ['csvtk', 'mutate']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('csvtk_mutate.out',)
    DOCUMENTATION_URL = 'https://github.com/shenwei356/csvtk'
    REQUIRED_EXECUTABLES = ['csvtk']
    REQUIRED_CONDA_PACKAGES = ['csvtk']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'table': ("FILE", {"description": 'Input table file'}),
                "name": ('STRING', {'description': 'new column name', 'default': ''}),
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
                "after": ('STRING', {'description': 'insert the new column right after the given column name', 'default': ''}),
                "at": ('INT', {'description': 'where the new column should appear, 1 for the 1st column, 0 for the last column', 'default': ''}),
                "before": ('STRING', {'description': 'insert the new column right before the given column name', 'default': ''}),
                "fields": ('STRING', {'description': 'select only these fields. e.g -f 1,2 or -f columnA,columnB', 'default': '1'}),
                "ignore_case": ('BOOLEAN', {'description': 'ignore case', 'default': False}),
                "na": ('BOOLEAN', {'description': 'for unmatched data, use blank instead of original data', 'default': False}),
                "pattern": ('STRING', {'description': 'search regular expression with capture bracket. e.g.', 'default': '^(.+)$'}),
                "remove": ('BOOLEAN', {'description': 'remove input column', 'default': False}),
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
