"""``seqkit fa2fq``: retrieve corresponding FASTQ records by a FASTA file.

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: 26d892336082e4aaeb2d9e5d2140bee324775109b8e8b9d7091b5732329fb569

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitFa2fqNode(SeqkitBase):
    """retrieve corresponding FASTQ records by a FASTA file"""

    NODE_ID = 'seqkit_fa2fq'
    DISPLAY_NAME = 'seqkit fa2fq'
    SUBCOMMAND = 'fa2fq'
    DESCRIPTION = 'retrieve corresponding FASTQ records by a FASTA file'
    SEARCH_ALIASES = ['seqkit', 'fa2fq']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqkit_fa2fq.out',)
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/seqkit/'
    REQUIRED_EXECUTABLES = ['seqkit']
    REQUIRED_CONDA_PACKAGES = ['seqkit']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ("FILE", {"description": 'Input FASTA/FASTQ file'}),
                "fasta_file": ('STRING', {'description': 'FASTA file)', 'default': ''}),
            },
            "optional": {
                "only_positive_strand": ('BOOLEAN', {'description': 'only search on positive strand', 'default': False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = ['seqkit', cls.SUBCOMMAND]
        # Required flags must be rendered too. Iterating only "optional" silently
        # dropped every empirically-required flag (csvtk mutate --name and friends).
        declared_types = cls.INPUT_TYPES()
        for category in ("required", "optional"):
            for name, spec in declared_types.get(category, {}).items():
                if name in ('sequence',):
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
        command.extend(['-o', str(output_dir / cls.OUTPUT_FILENAMES[0])])
        command.append(str(inputs.get('sequence', "")))
        return command
