"""``seqfu lanes``: Merge Illumina FASTQ lane files into uncompressed output files.

Generated from the tool's own --help output in the pinned seqfu seqfu 1.28.0 image.
Help page SHA-256: 186bddf26a1b163fbd67a51fbd2d6cf8f9951e8c8b204a071eb2d8cda91c6db4

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqfuBase


class SeqfuLanesNode(SeqfuBase):
    """Merge Illumina FASTQ lane files into uncompressed output files"""

    NODE_ID = 'seqfu_lanes'
    DISPLAY_NAME = 'seqfu lanes'
    SUBCOMMAND = 'lanes'
    DESCRIPTION = 'Merge Illumina FASTQ lane files into uncompressed output files'
    SEARCH_ALIASES = ['seqfu', 'lanes']
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("output_dir",)
    OUTPUT_FILENAMES = ()
    DOCUMENTATION_URL = 'https://telatin.github.io/seqfu2/'
    REQUIRED_EXECUTABLES = ['seqfu']
    REQUIRED_CONDA_PACKAGES = ['seqfu']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input_dir': ('DIRECTORY', {"description": "Input input dir"}),

            },
            "optional": {
                "extension": ('STRING', {'description': 'File extension', 'default': '.fastq'}),
                "file_separator": ('STRING', {'description': 'Field separator in filenames', 'default': '_'}),
                "comment_separator": ('STRING', {'description': 'String separating sequence name and its comment', 'default': 'TAB'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = ['seqfu', cls.SUBCOMMAND]
        # Required flags must be rendered too. Iterating only "optional" silently
        # dropped every empirically-required flag (csvtk mutate --name and friends).
        declared_types = cls.INPUT_TYPES()
        for category in ("required", "optional"):
            for name, spec in declared_types.get(category, {}).items():
                if name in ('input_dir',):
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
        command.extend(['--outdir', str(output_dir)])
        command.append(str(inputs.get('input_dir', "")))
        return command
