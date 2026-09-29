"""``seqkit faidx``: create the FASTA index file and extract subsequences.

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: 9de3c33adf79929f65afae592e097e3dcdb1efd74a99fb353db00a719cbd4b5b

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitFaidxNode(SeqkitBase):
    """create the FASTA index file and extract subsequences"""

    NODE_ID = 'seqkit_faidx'
    DISPLAY_NAME = 'seqkit faidx'
    SUBCOMMAND = 'faidx'
    DESCRIPTION = 'create the FASTA index file and extract subsequences'
    SEARCH_ALIASES = ['seqkit', 'faidx']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqkit_faidx.out',)
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
                "full_head": ('BOOLEAN', {'description': 'print full header line instead of just ID. New fasta index file ending with .seqkit.fai will be created', 'default': False}),
                "ignore_case": ('BOOLEAN', {'description': 'ignore case', 'default': False}),
                "immediate_output": ('BOOLEAN', {'description': 'print output immediately, do not use write buffer', 'default': False}),
                "region_file": ('STRING', {'description': 'file containing a list of regions', 'default': ''}),
                "update_faidx": ('BOOLEAN', {'description': 'update the fasta index file if it exists. Use this if you are not sure whether the fasta file changed', 'default': False}),
                "use_regexp": ('BOOLEAN', {'description': 'IDs are regular expression. But subseq region is not supported here.', 'default': False}),
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
