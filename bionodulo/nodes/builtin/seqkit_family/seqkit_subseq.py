"""``seqkit subseq``: get subsequences by region/gtf/bed, including flanking sequences..

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: 8c46aa5072f17c2f0927460080f64af52e0555585f793e92d6807aabe8f2bd07

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitSubseqNode(SeqkitBase):
    """get subsequences by region/gtf/bed, including flanking sequences."""

    NODE_ID = 'seqkit_subseq'
    DISPLAY_NAME = 'seqkit subseq'
    SUBCOMMAND = 'subseq'
    DESCRIPTION = 'get subsequences by region/gtf/bed, including flanking sequences.'
    SEARCH_ALIASES = ['seqkit', 'subseq']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqkit_subseq.out',)
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/seqkit/'
    REQUIRED_EXECUTABLES = ['seqkit']
    REQUIRED_CONDA_PACKAGES = ['seqkit']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ("FILE", {"description": 'Input FASTA/FASTQ file'}),
                "region": ('STRING', {'description': 'by region. e.g 1:12 for first 12 bases, -12:-1 for last 12 bases, 13:-1 for cutting first 12 bases. type "seqkit subseq -h" for more examples', 'default': ''}),
            },
            "optional": {
                "bed": ('STRING', {'description': 'by tab-delimited BED file', 'default': ''}),
                "chr": ('STRING', {'description': 'select limited sequence with sequence IDs when using --gtf or --bed (multiple value supported, case ignored)', 'default': ''}),
                "down_stream": ('INT', {'description': 'down stream length', 'default': ''}),
                "feature": ('STRING', {'description': 'select limited feature types (multiple value supported, case ignored, only works with GTF)', 'default': ''}),
                "gtf": ('STRING', {'description': 'by GTF (version 2.2) file', 'default': ''}),
                "gtf_tag": ('STRING', {'description': 'output this tag as sequence comment', 'default': 'gene_id'}),
                "only_flank": ('BOOLEAN', {'description': 'only return up/down stream sequence', 'default': False}),
                "region_coord": ('BOOLEAN', {'description': 'append coordinates to sequence ID for -r/--region', 'default': False}),
                "up_stream": ('INT', {'description': 'up stream length', 'default': ''}),
                "update_faidx": ('BOOLEAN', {'description': 'update the fasta index file if it exists. Use this if you are not sure whether the fasta file changed', 'default': False}),
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
