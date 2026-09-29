"""``seqkit watch``: monitoring and online histograms of sequence features.

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: ef3d5a6d0af57ccc3edbe0eb63632322d2a9da74e6b70b1786e3d2622fd2a8f0

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitWatchNode(SeqkitBase):
    """monitoring and online histograms of sequence features"""

    NODE_ID = 'seqkit_watch'
    DISPLAY_NAME = 'seqkit watch'
    SUBCOMMAND = 'watch'
    DESCRIPTION = 'monitoring and online histograms of sequence features'
    SEARCH_ALIASES = ['seqkit', 'watch']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqkit_watch.out',)
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
                "bins": ('INT', {'description': 'number of histogram bins', 'default': -1}),
                "delay": ('INT', {'description': 'sleep this many seconds after online plotting', 'default': 1}),
                "dump": ('BOOLEAN', {'description': 'print histogram data to stderr instead of plotting', 'default': False}),
                "fields": ('STRING', {'description': 'target fields, available values: ReadLen, MeanQual, GC, GCSkew (default "ReadLen")', 'default': ''}),
                "img": ('STRING', {'description': 'save histogram to this PDF/image file', 'default': ''}),
                "list_fields": ('BOOLEAN', {'description': 'print out a list of available fields', 'default': False}),
                "log": ('BOOLEAN', {'description': 'log10(x+1) transform numeric values', 'default': False}),
                "pass": ('BOOLEAN', {'description': 'pass through mode (write input to stdout)', 'default': False}),
                "print_freq": ('INT', {'description': 'print/report after this many records (-1 for print after EOF)', 'default': -1}),
                "qual_ascii_base": ('INT', {'description': 'ASCII BASE, 33 for Phred+33', 'default': 33}),
                "quiet_mode": ('BOOLEAN', {'description': 'supress all plotting to stderr', 'default': False}),
                "reset": ('BOOLEAN', {'description': 'reset histogram after every report', 'default': False}),
                "validate_seq": ('BOOLEAN', {'description': 'validate bases according to the alphabet', 'default': False}),
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
