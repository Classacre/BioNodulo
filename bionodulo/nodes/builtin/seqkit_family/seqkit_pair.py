"""``seqkit pair``: match up paired-end reads from two fastq files.

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: 7dcec8e7cc2832726b1e06544b40acf50e2a274bc18a46dabed9ca8dec121d31

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitPairNode(SeqkitBase):
    """match up paired-end reads from two fastq files"""

    NODE_ID = 'seqkit_pair'
    DISPLAY_NAME = 'seqkit pair'
    SUBCOMMAND = 'pair'
    DESCRIPTION = 'match up paired-end reads from two fastq files'
    SEARCH_ALIASES = ['seqkit', 'pair']
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("output_dir",)
    OUTPUT_FILENAMES = ()
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/seqkit/'
    REQUIRED_EXECUTABLES = ['seqkit']
    REQUIRED_CONDA_PACKAGES = ['seqkit']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'read1': ('FILE', {"description": "Input read1"}),
                'read2': ('FILE', {"description": "Input read2"}),

            },
            "optional": {
                "force": ('BOOLEAN', {'description': 'overwrite output directory', 'default': False}),
                "save_unpaired": ('BOOLEAN', {'description': 'save unpaired reads if there are', 'default': False}),
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
                if name in ('read1', 'read2'):
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
        command.extend(['--out-dir', str(output_dir)])
        command.extend(['--read1', str(inputs.get('read1', ""))])
        command.extend(['--read2', str(inputs.get('read2', ""))])
        return command
