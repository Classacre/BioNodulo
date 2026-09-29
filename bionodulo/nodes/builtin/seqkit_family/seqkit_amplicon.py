"""``seqkit amplicon``: extract amplicon (or specific region around it) via primer(s)..

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: c59dcf4e6953f3438648a831803d58e7e73542ef95c3f67f660889ec38beabf9

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitAmpliconNode(SeqkitBase):
    """extract amplicon (or specific region around it) via primer(s)."""

    NODE_ID = 'seqkit_amplicon'
    DISPLAY_NAME = 'seqkit amplicon'
    SUBCOMMAND = 'amplicon'
    DESCRIPTION = 'extract amplicon (or specific region around it) via primer(s).'
    SEARCH_ALIASES = ['seqkit', 'amplicon']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqkit_amplicon.out',)
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
                "bed": ('BOOLEAN', {'description': 'output in BED6+1 format with amplicon as the 7th column', 'default': False}),
                "flanking_region": ('BOOLEAN', {'description': 'region is flanking region', 'default': False}),
                "forward": ('STRING', {'description': "forward primer (5'-primer-3'), degenerate bases allowed", 'default': ''}),
                "immediate_output": ('BOOLEAN', {'description': 'print output immediately, do not use write buffer', 'default': False}),
                "max_mismatch": ('INT', {'description': 'max mismatch when matching primers, no degenerate bases allowed', 'default': ''}),
                "only_positive_strand": ('BOOLEAN', {'description': 'only search on positive strand', 'default': False}),
                "output_mismatches": ('BOOLEAN', {'description': "append the total mismatches and mismatches of 5' end and 3' end", 'default': False}),
                "primer_file": ('STRING', {'description': '3- or 2-column tabular primer file, with first column as primer name', 'default': ''}),
                "region": ('STRING', {'description': 'specify region to return. type "seqkit amplicon -h" for detail', 'default': ''}),
                "reverse": ('STRING', {'description': "reverse primer (5'-primer-3'), degenerate bases allowed", 'default': ''}),
                "save_unmatched": ('BOOLEAN', {'description': 'also save records that do not match any primer', 'default': False}),
                "strict_mode": ('BOOLEAN', {'description': 'strict mode, i.e., discarding seqs not fully matching (shorter) given region range', 'default': False}),
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
