"""``seqkit rename``: rename duplicated IDs.

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: 73be6c2dd222f61929d779df76f40336b54746a3830fb7a546e823a1767906fb

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitRenameNode(SeqkitBase):
    """rename duplicated IDs"""

    NODE_ID = 'seqkit_rename'
    DISPLAY_NAME = 'seqkit rename'
    SUBCOMMAND = 'rename'
    DESCRIPTION = 'rename duplicated IDs'
    SEARCH_ALIASES = ['seqkit', 'rename']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqkit_rename.out',)
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
                "by_name": ('BOOLEAN', {'description': 'check duplication by full name instead of just id', 'default': False}),
                "force": ('BOOLEAN', {'description': 'overwrite output directory', 'default': False}),
                "multiple_outfiles": ('BOOLEAN', {'description': 'write results into separated files for multiple input files', 'default': False}),
                "out_dir": ('STRING', {'description': 'output directory', 'default': 'renamed'}),
                "rename_1st_rec": ('BOOLEAN', {'description': 'rename the first record as well', 'default': False}),
                "separator": ('STRING', {'description': 'separator between original ID/name and the counter', 'default': '_'}),
                "start_num": ('INT', {'description': 'starting count number for *duplicated* IDs/names, should be greater than zero (default 2)', 'default': ''}),
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
