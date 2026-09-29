"""``seqfu sort``: Sort sequences by size printing only unique sequences.

Generated from the tool's own --help output in the pinned seqfu seqfu 1.28.0 image.
Help page SHA-256: ba6ea2ca7309d6f9c783c5d7a460b92b26399570a963473b8750cd1a636e8fc0

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import SeqfuBase


class SeqfuSortNode(SeqfuBase):
    """Sort sequences by size printing only unique sequences"""

    NODE_ID = 'seqfu_sort'
    DISPLAY_NAME = 'seqfu sort'
    SUBCOMMAND = 'sort'
    DESCRIPTION = 'Sort sequences by size printing only unique sequences'
    SEARCH_ALIASES = ['seqfu', 'sort']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqfu_sort.out',)
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
                "prefix": ('STRING', {'description': 'Sequence prefix', 'default': ''}),
                "strip_comments": ('BOOLEAN', {'description': 'Remove sequence comments', 'default': False}),
                "asc": ('BOOLEAN', {'description': 'Ascending order', 'default': False}),
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
