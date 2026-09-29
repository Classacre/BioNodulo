"""``seqkit sliding``: extract subsequences in sliding windows.

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: f0309453966cfb1eb9e45bec7c414751650b23c81a121cf5f7297aa567049069

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitSlidingNode(SeqkitBase):
    """extract subsequences in sliding windows"""

    NODE_ID = 'seqkit_sliding'
    DISPLAY_NAME = 'seqkit sliding'
    SUBCOMMAND = 'sliding'
    DESCRIPTION = 'extract subsequences in sliding windows'
    SEARCH_ALIASES = ['seqkit', 'sliding']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqkit_sliding.out',)
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/seqkit/'
    REQUIRED_EXECUTABLES = ['seqkit']
    REQUIRED_CONDA_PACKAGES = ['seqkit']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ("FILE", {"description": 'Input FASTA/FASTQ file'}),
                "step": ('INT', {'description': 'step size', 'default': ''}),
                "window": ('INT', {'description': 'window size', 'default': ''}),
            },
            "optional": {
                "circular": ('BOOLEAN', {'description': 'circular genome (same to -C/--circular-genome)', 'default': False}),
                "circular_genome": ('BOOLEAN', {'description': 'circular genome (same to -c/--circular)', 'default': False}),
                "greedy": ('BOOLEAN', {'description': 'greedy mode, i.e., exporting last subsequences even shorter than the windows size', 'default': False}),
                "suffix": ('STRING', {'description': 'suffix added to the sequence ID', 'default': '_sliding'}),
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
