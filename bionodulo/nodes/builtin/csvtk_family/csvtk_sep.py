"""``csvtk sep``: separate column into multiple columns.

Generated from the tool's own --help output in the pinned csvtk v0.31.0 image.
Help page SHA-256: fcdb8ced660a778beebadb2409aafe3e07795bba80709bf60630658b981aace2

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import CsvtkBase


class CsvtkSepNode(CsvtkBase):
    """separate column into multiple columns"""

    NODE_ID = 'csvtk_sep'
    DISPLAY_NAME = 'csvtk sep'
    SUBCOMMAND = 'sep'
    DESCRIPTION = 'separate column into multiple columns'
    SEARCH_ALIASES = ['csvtk', 'sep']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('csvtk_sep.out',)
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
                "drop": ('BOOLEAN', {'description': 'drop extra data, exclusive with --merge', 'default': False}),
                "fields": ('STRING', {'description': 'select only these fields. e.g -f 1,2 or -f columnA,columnB', 'default': '1'}),
                "ignore_case": ('BOOLEAN', {'description': 'ignore case', 'default': False}),
                "merge": ('BOOLEAN', {'description': 'only splits at most N times, exclusive with --drop', 'default': False}),
                "na": ('STRING', {'description': 'content for filling NA data', 'default': ''}),
                "names": ('STRING', {'description': 'new column names', 'default': ''}),
                "num_cols": ('INT', {'description': 'preset number of new created columns', 'default': ''}),
                "remove": ('BOOLEAN', {'description': 'remove input column', 'default': False}),
                "sep": ('STRING', {'description': 'separator', 'default': ''}),
                "use_regexp": ('BOOLEAN', {'description': 'separator is a regular expression', 'default': False}),
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
