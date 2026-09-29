"""``seqfu tabcheck``: Inspect TSV and CSV files for valid columns.

Generated from the tool's own --help output in the pinned seqfu seqfu 1.28.0 image.
Help page SHA-256: 2fd4b2b03bad672f42f9cf594bad5ba59e9889d77b3f70b7e833ba7e0d84ba67

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import SeqfuBase


class SeqfuTabcheckNode(SeqfuBase):
    """Inspect TSV and CSV files for valid columns"""

    NODE_ID = 'seqfu_tabcheck'
    DISPLAY_NAME = 'seqfu tabcheck'
    SUBCOMMAND = 'tabcheck'
    DESCRIPTION = 'Inspect TSV and CSV files for valid columns'
    SEARCH_ALIASES = ['seqfu', 'tabcheck']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqfu_tabcheck.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://telatin.github.io/seqfu2/'
    REQUIRED_EXECUTABLES = ['seqfu']
    REQUIRED_CONDA_PACKAGES = ['seqfu']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input sequence file'}),

            },
            "optional": {
                "separator": ('STRING', {'description': "Character separating the values, 'tab' for tab and 'auto' to try tab or commas [default: auto]", 'default': ''}),
                "comment": ('STRING', {'description': 'Comment/Header char', 'default': '#'}),
                "inspect": ('BOOLEAN', {'description': 'Gather more informations on column content [if valid column]', 'default': False}),
                "header": ('BOOLEAN', {'description': 'Print a header to the report', 'default': False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['seqfu', cls.SUBCOMMAND]
        # Required flags must be rendered too. Iterating only "optional" silently
        # dropped every empirically-required flag (csvtk mutate --name and friends).
        declared_types = cls.INPUT_TYPES()
        for category in ("required", "optional"):
            for name, spec in declared_types.get(category, {}).items():
                if name in ('input',):
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
        command.append(str(inputs.get('input', "")))
        return command
