"""``seqfu amplicheck``: Inspect paired-end amplicon FASTQ files and write QC recommendations.

Generated from the tool's own --help output in the pinned seqfu seqfu 1.28.0 image.
Help page SHA-256: 9a81f0a5c0a964211ea882631f4c00e220a736e2a40a67000472c32533dd3b15

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqfuBase


class SeqfuAmplicheckNode(SeqfuBase):
    """Inspect paired-end amplicon FASTQ files and write QC recommendations"""

    NODE_ID = 'seqfu_amplicheck'
    DISPLAY_NAME = 'seqfu amplicheck'
    SUBCOMMAND = 'amplicheck'
    DESCRIPTION = 'Inspect paired-end amplicon FASTQ files and write QC recommendations'
    SEARCH_ALIASES = ['seqfu', 'amplicheck']
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
                'read1': ('FILE', {"description": "Input read1"}),
                'read2': ('FILE', {"description": "Input read2"}),

            },
            "optional": {
                "fwd_tag": ('STRING', {'description': 'Forward read tag for batch pairing', 'default': '_R1'}),
                "rev_tag": ('STRING', {'description': 'Reverse read tag for batch pairing', 'default': '_R2'}),
                "max_reads": ('INT', {'description': 'Stop after INT scanned read pairs per sample; 0 = all', 'default': 500000}),
                "subsample": ('FLOAT', {'description': 'Deterministic fraction of scanned pairs to analyze', 'default': 1.0}),
                "only": ('STRING', {'description': 'Run only comma-separated stages: primers,length,quality,merge,sweep', 'default': ''}),
                "skip": ('STRING', {'description': 'Skip comma-separated stages; "overlap" is accepted as "merge"', 'default': ''}),
                "skip_primers": ('BOOLEAN', {'description': 'Shortcut for --skip primers', 'default': False}),
                "skip_overlap": ('BOOLEAN', {'description': 'Shortcut for --skip merge', 'default': False}),
                "sweep": ('BOOLEAN', {'description': 'Run truncLen/maxEE sweep', 'default': False}),
                "truncLen_grid": ('STRING', {'description': 'Comma-separated truncLen values for --sweep; 0 = no truncation', 'default': ''}),
                "maxEE_grid": ('STRING', {'description': 'Comma-separated maxEE values for --sweep', 'default': ''}),
                "amplicon": ('STRING', {'description': 'One of auto, 16s, its', 'default': 'auto'}),
                "json": ('BOOLEAN', {'description': 'Write JSON report (default)', 'default': False}),
                "no_json": ('BOOLEAN', {'description': 'Do not write JSON report', 'default': False}),
                "text": ('BOOLEAN', {'description': 'Write human-readable report.txt', 'default': False}),
                "plot": ('BOOLEAN', {'description': 'Write self-contained HTML quality plots', 'default': False}),
                "threads": ('INT', {'description': 'Number of sample pairs to process in parallel', 'default': 1}),
                "min_overlap": ('INT', {'description': 'Minimum overlap length for native estimator', 'default': 12}),
                "min_id": ('FLOAT', {'description': 'Minimum overlap identity for native estimator', 'default': 0.85}),
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
        command.extend(['--outdir', str(output_dir)])
        command.append(str(inputs.get('read1', "")))
        command.append(str(inputs.get('read2', "")))
        return command
