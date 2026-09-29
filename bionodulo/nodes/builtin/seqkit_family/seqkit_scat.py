"""``seqkit scat``: real time recursive concatenation and streaming of fastx files.

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: 7b0e5428ccd903a0569f13568c4021154615b3f5e97e9a7c23db7c9f522ff5d9

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitScatNode(SeqkitBase):
    """real time recursive concatenation and streaming of fastx files"""

    NODE_ID = 'seqkit_scat'
    DISPLAY_NAME = 'seqkit scat'
    SUBCOMMAND = 'scat'
    DESCRIPTION = 'real time recursive concatenation and streaming of fastx files'
    SEARCH_ALIASES = ['seqkit', 'scat']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqkit_scat.out',)
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
                "allow_gaps": ('BOOLEAN', {'description': 'allow gap character (-) in sequences', 'default': False}),
                "delta": ('INT', {'description': 'minimum size increase in kilobytes to trigger parsing', 'default': 5}),
                "drop_time": ('STRING', {'description': 'Notification drop interval', 'default': '500ms'}),
                "find_only": ('BOOLEAN', {'description': 'concatenate existing files and quit', 'default': False}),
                "format": ('STRING', {'description': 'input and output format: fastq or fasta (fastq)', 'default': 'fastq'}),
                "gz_only": ('BOOLEAN', {'description': 'only look for gzipped files (.gz suffix)', 'default': False}),
                "in_format": ('STRING', {'description': 'input format: fastq or fasta (fastq)', 'default': ''}),
                "out_format": ('STRING', {'description': 'output format: fastq or fasta', 'default': ''}),
                "qual_ascii_base": ('INT', {'description': 'ASCII BASE, 33 for Phred+33', 'default': 33}),
                "regexp": ('STRING', {'description': 'regexp for watched files, by default guessed from the input format', 'default': ''}),
                "time_limit": ('STRING', {'description': 'quit after inactive for this time period', 'default': ''}),
                "wait_pid": ('INT', {'description': 'after process with this PID exited', 'default': -1}),
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
