"""``seqkit concat``: concatenate sequences with same ID from multiple files.

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: 9ce02ef1470a6baa3683ac3aa466ea89abde02354790506dcf18b03b45c08b5a

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitConcatNode(SeqkitBase):
    """concatenate sequences with same ID from multiple files"""

    NODE_ID = 'seqkit_concat'
    DISPLAY_NAME = 'seqkit concat'
    SUBCOMMAND = 'concat'
    DESCRIPTION = 'concatenate sequences with same ID from multiple files'
    SEARCH_ALIASES = ['seqkit', 'concat']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqkit_concat.out',)
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/seqkit/'
    REQUIRED_EXECUTABLES = ['seqkit']
    REQUIRED_CONDA_PACKAGES = ['seqkit']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ("FILE", {"description": 'Input FASTA/FASTQ file'}),

            },
            "optional": {
                "fill": ('STRING', {'description': 'fill with N bases/residues for IDs missing in some files when using -f/--full', 'default': ''}),
                "full": ('BOOLEAN', {'description': 'keep all sequences, like full/outer join', 'default': False}),
                "separator": ('STRING', {'description': 'separator for descriptions of records with the same ID', 'default': '|'}),
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
