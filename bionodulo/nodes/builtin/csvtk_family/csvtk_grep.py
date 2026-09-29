"""``csvtk grep``: grep data by selected fields with patterns/regular expressions.

Generated from the tool's own --help output in the pinned csvtk v0.31.0 image.
Help page SHA-256: c257fa493a6b0b18eb7ff0d7291198f28ce31c172ab0d5961807a550444cdb49

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import CsvtkBase


class CsvtkGrepNode(CsvtkBase):
    """grep data by selected fields with patterns/regular expressions"""

    NODE_ID = 'csvtk_grep'
    DISPLAY_NAME = 'csvtk grep'
    SUBCOMMAND = 'grep'
    DESCRIPTION = 'grep data by selected fields with patterns/regular expressions'
    SEARCH_ALIASES = ['csvtk', 'grep']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('csvtk_grep.out',)
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
                "delete_matched": ('BOOLEAN', {'description': 'delete a pattern right after being matched, this keeps the firstly matched data and speedups when using regular expressions', 'default': False}),
                "fields": ('STRING', {'description': 'comma separated key fields, column name or index. e.g. -f 1-3 or -f id,id2 or -F -f "group*" (default "1")', 'default': ''}),
                "fuzzy_fields": ('BOOLEAN', {'description': 'using fuzzy fields, e.g., -F -f "*name" or -F -f "id123*"', 'default': False}),
                "ignore_case": ('BOOLEAN', {'description': 'ignore case', 'default': False}),
                "immediate_output": ('BOOLEAN', {'description': 'print output immediately, do not use write buffer', 'default': False}),
                "invert": ('BOOLEAN', {'description': 'invert match', 'default': False}),
                "line_number": ('BOOLEAN', {'description': 'print line number as the first column ("n")', 'default': False}),
                "no_highlight": ('BOOLEAN', {'description': 'no highlight', 'default': False}),
                "pattern": ('STRING', {'description': 'query pattern (multiple values supported). Attention: use double quotation marks for patterns containing comma, e.g., -p \'"A{2,}"\'', 'default': ''}),
                "pattern_file": ('STRING', {'description': 'pattern files (one pattern per line)', 'default': ''}),
                "use_regexp": ('BOOLEAN', {'description': 'patterns are regular expression', 'default': False}),
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
