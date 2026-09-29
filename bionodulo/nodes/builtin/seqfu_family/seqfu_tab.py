"""``seqfu tab``: Convert FASTQ to TSV and viceversa. Single end is a 4 columns table (name, comme.

Generated from the tool's own --help output in the pinned seqfu seqfu 1.28.0 image.
Help page SHA-256: dc3a496ac6eab72ebb00dfd8dba904b97c4ac5cef4f68f1d407a9fbf582907a9

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import SeqfuBase


class SeqfuTabNode(SeqfuBase):
    """Convert FASTQ to TSV and viceversa. Single end is a 4 columns table (name, comment, seq, qual),"""

    NODE_ID = 'seqfu_tab'
    DISPLAY_NAME = 'seqfu tab'
    SUBCOMMAND = 'tab'
    DESCRIPTION = 'Convert FASTQ to TSV and viceversa. Single end is a 4 columns table (name, comment, seq, qual),'
    SEARCH_ALIASES = ['seqfu', 'tab']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqfu_tab.out',)
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
                "interleaved": ('BOOLEAN', {'description': 'Input is interleaved (paired-end)', 'default': False}),
                "detabulate": ('BOOLEAN', {'description': 'Convert TSV to FASTQ (if reading from file is autodetected)', 'default': False}),
                "comment_sep": ('STRING', {'description': 'Separator between name and comment (default: tab)', 'default': ''}),
                "field_sep": ('STRING', {'description': 'Field separator when deinterleaving (default: tab)', 'default': ''}),
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
