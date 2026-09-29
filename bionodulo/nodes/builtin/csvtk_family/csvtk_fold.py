"""``csvtk fold``: fold multiple values of a field into cells of groups.

Generated from the tool's own --help output in the pinned csvtk v0.31.0 image.
Help page SHA-256: 55ef769dec70d194c5d0b89dfeddc7d5acf320e82ef649ae32a3582f453aa652

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import CsvtkBase


class CsvtkFoldNode(CsvtkBase):
    """fold multiple values of a field into cells of groups"""

    NODE_ID = 'csvtk_fold'
    DISPLAY_NAME = 'csvtk fold'
    SUBCOMMAND = 'fold'
    DESCRIPTION = 'fold multiple values of a field into cells of groups'
    SEARCH_ALIASES = ['csvtk', 'fold']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('csvtk_fold.out',)
    DOCUMENTATION_URL = 'https://github.com/shenwei356/csvtk'
    REQUIRED_EXECUTABLES = ['csvtk']
    REQUIRED_CONDA_PACKAGES = ['csvtk']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'table': ("FILE", {"description": 'Input table file'}),
                "vfield": ('STRING', {'description': 'value field for folding', 'default': ''}),
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
                "fields": ('STRING', {'description': 'key fields for grouping. e.g -f 1,2 or -f columnA,columnB', 'default': '1'}),
                "fuzzy_fields": ('BOOLEAN', {'description': 'using fuzzy fields (only for key fields), e.g., -F -f "*name" or -F -f "id123*"', 'default': False}),
                "ignore_case": ('BOOLEAN', {'description': 'ignore case', 'default': False}),
                "separater": ('STRING', {'description': 'separater for folded values', 'default': '; '}),
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
