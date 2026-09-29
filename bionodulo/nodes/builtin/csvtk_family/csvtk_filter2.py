"""``csvtk filter2``: filter rows by awk-like arithmetic/string expressions.

Generated from the tool's own --help output in the pinned csvtk v0.31.0 image.
Help page SHA-256: c71898eb35ae779822578753eb2eb9d42a42e43705e34335fa8884bc2fd87379

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import CsvtkBase


class CsvtkFilter2Node(CsvtkBase):
    """filter rows by awk-like arithmetic/string expressions"""

    NODE_ID = 'csvtk_filter2'
    DISPLAY_NAME = 'csvtk filter2'
    SUBCOMMAND = 'filter2'
    DESCRIPTION = 'filter rows by awk-like arithmetic/string expressions'
    SEARCH_ALIASES = ['csvtk', 'filter2']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('csvtk_filter2.out',)
    DOCUMENTATION_URL = 'https://github.com/shenwei356/csvtk'
    REQUIRED_EXECUTABLES = ['csvtk']
    REQUIRED_CONDA_PACKAGES = ['csvtk']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'table': ("FILE", {"description": 'Input table file'}),
                "filter": ('STRING', {'description': 'awk-like filter condition. e.g. \'$age>12\' or \'$1 > $3\' or \'$name=="abc"\' or \'$1 % 2 == 0\'', 'default': ''}),
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
                "line_number": ('BOOLEAN', {'description': 'print line number as the first column ("n")', 'default': False}),
                "numeric_as_string": ('BOOLEAN', {'description': 'treat even numeric fields as strings to avoid converting big numbers into scientific notation', 'default': False}),
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
