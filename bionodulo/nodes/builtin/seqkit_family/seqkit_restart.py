"""``seqkit restart``: reset start position (rotate) for circular genomes.

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: cdddd7f1193892b57ec0809e50343a9d0a6cd3d0df4eb51f81dd5e65ca4fd252

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitRestartNode(SeqkitBase):
    """reset start position (rotate) for circular genomes"""

    NODE_ID = 'seqkit_restart'
    DISPLAY_NAME = 'seqkit restart'
    SUBCOMMAND = 'restart'
    DESCRIPTION = 'reset start position (rotate) for circular genomes'
    SEARCH_ALIASES = ['seqkit', 'restart']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqkit_restart.out',)
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/seqkit/'
    REQUIRED_EXECUTABLES = ['seqkit']
    REQUIRED_CONDA_PACKAGES = ['seqkit']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ("FILE", {"description": 'Input FASTA/FASTQ file'}),
                "new_start": ('INT', {'description': 'new start position (1-based, supporting negative value counting from the end) (default 1)', 'default': ''}),
            },
            "optional": {
                "ignore_case": ('BOOLEAN', {'description': 'ignore case when searching the custom starting subsequence', 'default': False}),
                "max_mismatch": ('INT', {'description': 'max mismatch when searching the custom starting subsequence', 'default': ''}),
                "start_with": ('STRING', {'description': 'rotate the genome to make it starting with the given subsequence', 'default': ''}),
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
