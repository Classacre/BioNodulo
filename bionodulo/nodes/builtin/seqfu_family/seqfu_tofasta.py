"""``seqfu tofasta``: Convert various sequence formats to FASTA format..

Generated from the tool's own --help output in the pinned seqfu seqfu 1.28.0 image.
Help page SHA-256: a4dd6a8a8684f6fb42eeb989c55ef2753b7b51b7d1ff559ac4a4b7b3fe03dadd

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqfuBase


class SeqfuTofastaNode(SeqfuBase):
    """Convert various sequence formats to FASTA format."""

    NODE_ID = 'seqfu_tofasta'
    DISPLAY_NAME = 'seqfu tofasta'
    SUBCOMMAND = 'tofasta'
    DESCRIPTION = 'Convert various sequence formats to FASTA format.'
    SEARCH_ALIASES = ['seqfu', 'tofasta']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqfu_tofasta.out',)
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
                "replace_iupac": ('BOOLEAN', {'description': "Replace non-IUPAC characters with 'N'", 'default': False}),
                "to_lowercase": ('BOOLEAN', {'description': 'Convert sequences to lowercase', 'default': False}),
                "to_uppercase": ('BOOLEAN', {'description': 'Convert sequences to uppercase', 'default': False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
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
        command.extend(['--output', str(output_dir / cls.OUTPUT_FILENAMES[0])])
        command.append(str(inputs.get('input', "")))
        return command
