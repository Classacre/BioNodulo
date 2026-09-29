"""``seqkit sum``: compute message digest for all sequences in FASTA/Q files.

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: 4c22406e428e8e3392b2acb391f09354910987c53dbeda47b6bb10f5e6d35312

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitSumNode(SeqkitBase):
    """compute message digest for all sequences in FASTA/Q files"""

    NODE_ID = 'seqkit_sum'
    DISPLAY_NAME = 'seqkit sum'
    SUBCOMMAND = 'sum'
    DESCRIPTION = 'compute message digest for all sequences in FASTA/Q files'
    SEARCH_ALIASES = ['seqkit', 'sum']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqkit_sum.out',)
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
                "all": ('BOOLEAN', {'description': 'show all information, including the sequences length and the number of sequences', 'default': False}),
                "basename": ('BOOLEAN', {'description': 'only output basename of files', 'default': False}),
                "circular": ('BOOLEAN', {'description': 'the file contains a single cicular genome sequence', 'default': False}),
                "gap_letters": ('STRING', {'description': 'gap letters to delete with the flag -g/--remove-gaps', 'default': '- \\t.*'}),
                "kmer_size": ('INT', {'description': 'k-mer size for processing circular genomes', 'default': 1000}),
                "remove_gaps": ('BOOLEAN', {'description': 'remove gap characters set in the option -G/gap-letters', 'default': False}),
                "rna2dna": ('BOOLEAN', {'description': 'convert RNA to DNA', 'default': False}),
                "single_strand": ('BOOLEAN', {'description': 'only consider the positive strand of a circular genome, e.g., ssRNA virus genomes', 'default': False}),
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
