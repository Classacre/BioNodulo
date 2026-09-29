"""``csvtk join``: join files by selected fields (inner, left and outer join)..

Generated from the tool's own --help output in the pinned csvtk v0.31.0 image.
Help page SHA-256: e9bc12fa4d0df8eabce872bb6202612c6740a6f2671f0a36a82d1c914a6fb236

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import CsvtkBase


class CsvtkJoinNode(CsvtkBase):
    """join files by selected fields (inner, left and outer join)."""

    NODE_ID = 'csvtk_join'
    DISPLAY_NAME = 'csvtk join'
    SUBCOMMAND = 'join'
    DESCRIPTION = 'join files by selected fields (inner, left and outer join).'
    SEARCH_ALIASES = ['csvtk', 'join']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('csvtk_join.out',)
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
                "fields": ('STRING', {'description': 'Semicolon separated key fields of all files, if given one, we think all the files have the same key columns. Fields of different files should be separated by ";", e.g -f "1;2" or -f "A,B;C,D" or -f id', 'default': ''}),
                "fuzzy_fields": ('BOOLEAN', {'description': 'using fuzzy fields, e.g., -F -f "*name" or -F -f "id123*"', 'default': False}),
                "ignore_case": ('BOOLEAN', {'description': 'ignore case', 'default': False}),
                "ignore_null": ('BOOLEAN', {'description': 'do not match NULL values', 'default': False}),
                "keep_unmatched": ('BOOLEAN', {'description': 'keep unmatched data of the first file (left join)', 'default': False}),
                "left_join": ('BOOLEAN', {'description': 'left join, equals to -k/--keep-unmatched, exclusive with --outer-join', 'default': False}),
                "na": ('STRING', {'description': 'content for filling NA data', 'default': ''}),
                "only_duplicates": ('BOOLEAN', {'description': 'add filenames as colname prefixes or add custom suffixes only for duplicated colnames', 'default': False}),
                "outer_join": ('BOOLEAN', {'description': 'outer join, exclusive with --left-join', 'default': False}),
                "prefix_filename": ('BOOLEAN', {'description': "add each filename as a prefix to each colname. if there's no header row, we'll add one", 'default': False}),
                "prefix_trim_ext": ('BOOLEAN', {'description': 'trim extension when adding filename as colname prefix', 'default': False}),
                "suffix": ('STRING', {'description': 'add suffixes to colnames from each file', 'default': ''}),
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
