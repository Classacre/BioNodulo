"""``csvtk fmtdate``: format date of selected fields.

Generated from the tool's own --help output in the pinned csvtk v0.31.0 image.
Help page SHA-256: 6cad4d05941de39ec1efb1873c1a3b093b71077583dd8833da41a023be5328ab

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import CsvtkBase


class CsvtkFmtdateNode(CsvtkBase):
    """format date of selected fields"""

    NODE_ID = 'csvtk_fmtdate'
    DISPLAY_NAME = 'csvtk fmtdate'
    SUBCOMMAND = 'fmtdate'
    DESCRIPTION = 'format date of selected fields'
    SEARCH_ALIASES = ['csvtk', 'fmtdate']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('csvtk_fmtdate.out',)
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
                "fields": ('STRING', {'description': 'select only these fields. e.g -f 1,2 or -f columnA,columnB', 'default': '1'}),
                "format": ('STRING', {'description': 'output date format in MS Excel (TM) syntax, type "csvtk fmtdate -h" for details (default "YYYY-MM-DD hh:mm:ss")', 'default': ''}),
                "fuzzy_fields": ('BOOLEAN', {'description': 'using fuzzy fields, e.g., -F -f "*name" or -F -f "id123*"', 'default': False}),
                "keep_unparsed": ('BOOLEAN', {'description': 'keep the key as value when no value found for the key', 'default': False}),
                "time_zone": ('STRING', {'description': 'timezone aka "Asia/Shanghai" or "America/Los_Angeles" formatted time-zone, type "csvtk fmtdate -h" for details', 'default': ''}),
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
