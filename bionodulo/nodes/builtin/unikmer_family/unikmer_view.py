"""``unikmer view``: Read and output binary format to plain text.

Generated from the tool's own --help output in the pinned unikmer 0.20.0 image.
Help page SHA-256: 9c892e600d6233dceb277125c56d8a0aa7dad6974202d26dd0a82028b5df5031

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import UnikmerBase


class UnikmerViewNode(UnikmerBase):
    """Read and output binary format to plain text"""

    NODE_ID = 'unikmer_view'
    DISPLAY_NAME = 'unikmer view'
    SUBCOMMAND = 'view'
    DESCRIPTION = 'Read and output binary format to plain text'
    SEARCH_ALIASES = ['unikmer', 'view']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('unikmer_view.out',)
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/unikmer/'
    REQUIRED_EXECUTABLES = ['unikmer']
    REQUIRED_CONDA_PACKAGES = ['unikmer']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input k-mer file (.unik) or FASTA/Q file'}),

            },
            "optional": {
                "fasta": ('BOOLEAN', {'description': 'output in FASTA format, with encoded integer as FASTA header', 'default': False}),
                "fastq": ('BOOLEAN', {'description': 'output in FASTQ format, with encoded integer as FASTQ header', 'default': False}),
                "genome": ('STRING', {'description': 'genomes in (gzipped) fasta file(s) for decoding hashed k-mers', 'default': ''}),
                "show_code": ('BOOLEAN', {'description': 'show encoded integer along with k-mer', 'default': False}),
                "show_code_only": ('BOOLEAN', {'description': 'only show encoded integers, faster than cutting from result of -n/--show-cde', 'default': False}),
                "show_taxid": ('BOOLEAN', {'description': 'show taxid', 'default': False}),
                "show_taxid_only": ('BOOLEAN', {'description': 'show taxid only', 'default': False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = ['unikmer', cls.SUBCOMMAND]
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
        command.extend(['--out-file', str(output_dir / cls.OUTPUT_FILENAMES[0])])
        command.append(str(inputs.get('input', "")))
        return command
