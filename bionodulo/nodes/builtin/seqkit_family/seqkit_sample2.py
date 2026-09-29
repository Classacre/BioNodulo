"""``seqkit sample2``: sample sequences by number or proportion (version 2)..

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: 3c521daefbcbd343edbecb76e12ad5fbe6528a9cb98f37a445f19d1871e27286

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitSample2Node(SeqkitBase):
    """sample sequences by number or proportion (version 2)."""

    NODE_ID = 'seqkit_sample2'
    DISPLAY_NAME = 'seqkit sample2'
    SUBCOMMAND = 'sample2'
    DESCRIPTION = 'sample sequences by number or proportion (version 2).'
    SEARCH_ALIASES = ['seqkit', 'sample2']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqkit_sample2.out',)
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/seqkit/'
    REQUIRED_EXECUTABLES = ['seqkit']
    REQUIRED_CONDA_PACKAGES = ['seqkit']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ("FILE", {"description": 'Input FASTA/FASTQ file'}),
                "number": ('INT', {'description': 'sample by number. SHOULD BE coupled with -2 flag (2-pass mode) when handling large FASTQ files.', 'default': ''}),
            },
            "optional": {
                "non_deterministic": ('BOOLEAN', {'description': 'use a time-based seed to generate non-deterministic (truly random) results', 'default': False}),
                "proportion": ('FLOAT', {'description': 'sample by proportion. Numbers would not be constant if not coupled with 2-pass mode.', 'default': ''}),
                "rand_seed": ('INT', {'description': 'random seed. For paired-end data, use the same seed across fastq files to sample the same read pairs (default 11)', 'default': ''}),
                "two_pass": ('BOOLEAN', {'description': '2-pass mode read files twice to lower memory usage. Not allowed when reading from stdin', 'default': False}),
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
