"""``seqkit shuffle``: shuffle sequences..

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: ef1e96386e2282ef40f242d88370c855191ea9337cb9c46550dc0bfbad3a1ad1

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitShuffleNode(SeqkitBase):
    """shuffle sequences."""

    NODE_ID = 'seqkit_shuffle'
    DISPLAY_NAME = 'seqkit shuffle'
    SUBCOMMAND = 'shuffle'
    DESCRIPTION = 'shuffle sequences.'
    SEARCH_ALIASES = ['seqkit', 'shuffle']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqkit_shuffle.out',)
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
                "keep_temp": ('BOOLEAN', {'description': 'keep temporary FASTA and .fai file when using 2-pass mode', 'default': False}),
                "non_deterministic": ('BOOLEAN', {'description': 'use a time-based seed to generate non-deterministic (truly random) results', 'default': False}),
                "rand_seed": ('INT', {'description': 'rand seed for shuffle', 'default': 23}),
                "tmp_dir": ('STRING', {'description': 'tmp directory for saving temporary FASTA and .fai file when using 2-pass mode (default "./")', 'default': ''}),
                "two_pass": ('BOOLEAN', {'description': 'two-pass mode read files twice to lower memory usage. (only for FASTA format)', 'default': False}),
                "update_faidx": ('BOOLEAN', {'description': 'update the fasta index file if it exists. Use this if you are not sure whether the fasta file changed', 'default': False}),
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
