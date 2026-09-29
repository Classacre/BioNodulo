"""``seqkit fish``: look for short sequences in larger sequences using local alignment.

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: a8b16b0c70e2678f80e1447fea135a32253d50795c11d0f156d9edf4972f2466

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitFishNode(SeqkitBase):
    """look for short sequences in larger sequences using local alignment"""

    NODE_ID = 'seqkit_fish'
    DISPLAY_NAME = 'seqkit fish'
    SUBCOMMAND = 'fish'
    DESCRIPTION = 'look for short sequences in larger sequences using local alignment'
    SEARCH_ALIASES = ['seqkit', 'fish']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqkit_fish.out',)
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
                "all": ('BOOLEAN', {'description': 'search all', 'default': False}),
                "aln_params": ('STRING', {'description': 'alignment parameters in format "<match>,<mismatch>,<gap_open>,<gap_extend>" (default "4,-4,-2,-1")', 'default': ''}),
                "invert": ('BOOLEAN', {'description': 'print out references not matching with any query', 'default': False}),
                "min_qual": ('FLOAT', {'description': 'minimum mapping quality', 'default': 5.0}),
                "out_bam": ('STRING', {'description': 'save aligmnets to this BAM file (memory intensive)', 'default': ''}),
                "pass": ('BOOLEAN', {'description': 'pass through mode (write input to stdout)', 'default': False}),
                "print_aln": ('BOOLEAN', {'description': 'print sequence alignments', 'default': False}),
                "print_desc": ('BOOLEAN', {'description': 'print full sequence header', 'default': False}),
                "query_fastx": ('STRING', {'description': 'query fasta', 'default': ''}),
                "query_sequences": ('STRING', {'description': 'query sequences', 'default': ''}),
                "ranges": ('STRING', {'description': 'target ranges, for example: ":10,30:40,-20:"', 'default': ''}),
                "stranded": ('BOOLEAN', {'description': 'search + strand only', 'default': False}),
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
