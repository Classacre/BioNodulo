"""``seqkit bam``: monitoring and online histograms of BAM record features.

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: cb7ad6e862216244635e3e88057c4e00bcd12c63fd0527bbf6b90b99cd59e5b8

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitBamNode(SeqkitBase):
    """monitoring and online histograms of BAM record features"""

    NODE_ID = 'seqkit_bam'
    DISPLAY_NAME = 'seqkit bam'
    SUBCOMMAND = 'bam'
    DESCRIPTION = 'monitoring and online histograms of BAM record features'
    SEARCH_ALIASES = ['seqkit', 'bam']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqkit_bam.out',)
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
                "bundle": ('INT', {'description': 'partition BAM file into loci (-1) or bundles with this minimum size', 'default': ''}),
                "count": ('STRING', {'description': 'count reads per reference and save to this file', 'default': ''}),
                "delay": ('INT', {'description': 'sleep this many seconds after plotting', 'default': 1}),
                "dump": ('BOOLEAN', {'description': 'print histogram data to stderr instead of plotting', 'default': False}),
                "exclude_ids": ('STRING', {'description': 'exclude records with IDs contained in this file', 'default': ''}),
                "exec_after": ('STRING', {'description': 'execute command after reporting', 'default': ''}),
                "exec_before": ('STRING', {'description': 'execute command before reporting', 'default': ''}),
                "field": ('STRING', {'description': 'target fields', 'default': ''}),
                "grep_ids": ('STRING', {'description': 'only keep records with IDs contained in this file', 'default': ''}),
                "idx_count": ('BOOLEAN', {'description': 'fast read per reference counting based on the BAM index', 'default': False}),
                "idx_stat": ('BOOLEAN', {'description': 'fast statistics based on the BAM index', 'default': False}),
                "img": ('STRING', {'description': 'save histogram to this PDF/image file', 'default': ''}),
                "list_fields": ('BOOLEAN', {'description': 'list all available BAM record features', 'default': False}),
                "log": ('BOOLEAN', {'description': 'log10(x+1) transform numeric values', 'default': False}),
                "map_qual": ('INT', {'description': 'minimum mapping quality', 'default': ''}),
                "pass": ('BOOLEAN', {'description': 'passthrough mode (forward filtered BAM to output)', 'default': False}),
                "pretty": ('BOOLEAN', {'description': 'pretty print certain TSV outputs', 'default': False}),
                "prim_only": ('BOOLEAN', {'description': 'filter out non-primary alignment records', 'default': False}),
                "print_freq": ('INT', {'description': 'print/report after this many records (-1 for print after EOF)', 'default': -1}),
                "quiet_mode": ('BOOLEAN', {'description': 'supress all plotting to stderr', 'default': False}),
                "range_max": ('FLOAT', {'description': 'discard record with field (-f) value greater than this flag', 'default': 0.0}),
                "range_min": ('FLOAT', {'description': 'discard record with field (-f) value less than this flag', 'default': 0.0}),
                "reset": ('BOOLEAN', {'description': 'reset histogram after every report', 'default': False}),
                "silent_mode": ('BOOLEAN', {'description': 'supress TSV output to stderr', 'default': False}),
                "stat": ('BOOLEAN', {'description': 'print BAM satistics of the input files', 'default': False}),
                "tool": ('STRING', {'description': 'invoke toolbox in YAML format (see documentation)', 'default': ''}),
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
