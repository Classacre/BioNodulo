"""``csvtk rename2``: rename column names by regular expression.

Generated from the tool's own --help output in the pinned csvtk v0.31.0 image.
Help page SHA-256: 041986acd81afc9cc9eb3ed67c3817ca7192f7eedef90499c4c86514c6e2cf62

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import CsvtkBase


class CsvtkRename2Node(CsvtkBase):
    """rename column names by regular expression"""

    NODE_ID = 'csvtk_rename2'
    DISPLAY_NAME = 'csvtk rename2'
    SUBCOMMAND = 'rename2'
    DESCRIPTION = 'rename column names by regular expression'
    SEARCH_ALIASES = ['csvtk', 'rename2']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('csvtk_rename2.out',)
    DOCUMENTATION_URL = 'https://github.com/shenwei356/csvtk'
    REQUIRED_EXECUTABLES = ['csvtk']
    REQUIRED_CONDA_PACKAGES = ['csvtk']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'table': ("FILE", {"description": 'Input table file'}),
                "fields": ('STRING', {'description': 'select only these fields. e.g -f 1,2 or -f columnA,columnB', 'default': ''}),
                "pattern": ('STRING', {'description': 'search regular expression', 'default': ''}),
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
                "fuzzy_fields": ('BOOLEAN', {'description': 'using fuzzy fields, e.g., -F -f "*name" or -F -f "id123*"', 'default': False}),
                "ignore_case": ('BOOLEAN', {'description': 'ignore case', 'default': False}),
                "keep_key": ('BOOLEAN', {'description': 'keep the key as value when no value found for the key', 'default': False}),
                "key_capt_idx": ('INT', {'description': 'capture variable index of key (1-based)', 'default': 1}),
                "key_miss_repl": ('STRING', {'description': 'replacement for key with no corresponding value', 'default': ''}),
                "kv_file": ('STRING', {'description': 'tab-delimited key-value file for replacing key with value when using "{kv}" in -r (--replacement)', 'default': ''}),
                "kv_file_all_left_columns_as_value": ('BOOLEAN', {'description': 'treat all columns except 1th one as value for kv-file with more than 2 columns', 'default': False}),
                "nr_width": ('INT', {'description': 'minimum width for {nr} in flag -r/--replacement. e.g., formating "1" to "001" by --nr-width 3 (default 1)', 'default': ''}),
                "replacement": ('STRING', {'description': 'renamement. supporting capture variables.  e.g. $1 represents the text of the first submatch. ATTENTION: use SINGLE quote NOT double quotes in *nix OS or use the \\ escape character. Ascending number i', 'default': ''}),
                "start_num": ('INT', {'description': 'starting number when using {nr} in replacement', 'default': 1}),
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
