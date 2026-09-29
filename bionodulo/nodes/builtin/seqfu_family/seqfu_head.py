"""``seqfu head``: Select a number of sequences from the beginning of a file, optionally.

Generated from the tool's own --help output in the pinned seqfu seqfu 1.28.0 image.
Help page SHA-256: 773cd0a9fa0b1e919393122cdbbf90a9ec1ce8f0f2b776ae0a3848c9e987ac0e

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import SeqfuBase


class SeqfuHeadNode(SeqfuBase):
    """Select a number of sequences from the beginning of a file, optionally"""

    NODE_ID = 'seqfu_head'
    DISPLAY_NAME = 'seqfu head'
    SUBCOMMAND = 'head'
    DESCRIPTION = 'Select a number of sequences from the beginning of a file, optionally'
    SEARCH_ALIASES = ['seqfu', 'head']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqfu_head.out',)
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
                "num": ('FLOAT', {'description': 'Print the first NUM sequences', 'default': 10.0}),
                "skip": ('STRING', {'description': 'Print one sequence every SKIP (0 to disable)', 'default': '0'}),
                "prefix": ('STRING', {'description': 'Rename sequences with prefix + incremental number', 'default': ''}),
                "strip_comments": ('BOOLEAN', {'description': 'Remove comments', 'default': False}),
                "basename": ('BOOLEAN', {'description': 'Prepend basename to sequence name', 'default': False}),
                "print_last": ('BOOLEAN', {'description': 'Print the name of the last sequence to STDERR (Last:NAME)', 'default': False}),
                "fatal": ('BOOLEAN', {'description': 'Exit with error if fewer than NUM sequences are found', 'default': False}),
                "fasta": ('BOOLEAN', {'description': 'Force FASTA output', 'default': False}),
                "fastq": ('BOOLEAN', {'description': 'Force FASTQ output', 'default': False}),
                "sep": ('STRING', {'description': 'Sequence name fields separator', 'default': '_'}),
                "fastq_qual": ('INT', {'description': 'FASTQ default quality', 'default': 33}),
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
