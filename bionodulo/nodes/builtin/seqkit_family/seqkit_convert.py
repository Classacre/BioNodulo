"""``seqkit convert``: convert FASTQ quality encoding between Sanger, Solexa and Illumina.

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: 28d01a84bdc27093ea07728742dcc6f4d63eddd87ed7841b978b36a61e2d2357

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitConvertNode(SeqkitBase):
    """convert FASTQ quality encoding between Sanger, Solexa and Illumina"""

    NODE_ID = 'seqkit_convert'
    DISPLAY_NAME = 'seqkit convert'
    SUBCOMMAND = 'convert'
    DESCRIPTION = 'convert FASTQ quality encoding between Sanger, Solexa and Illumina'
    SEARCH_ALIASES = ['seqkit', 'convert']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqkit_convert.out',)
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
                "dry_run": ('BOOLEAN', {'description': 'dry run', 'default': False}),
                "force": ('BOOLEAN', {'description': 'for Illumina-1.8+ -> Sanger, truncate scores > 40 to 40', 'default': False}),
                "from": ('STRING', {'description': "source quality encoding. if not given, we'll guess it", 'default': ''}),
                "nrecords": ('INT', {'description': 'number of records for guessing quality encoding', 'default': 1000}),
                "thresh_B_in_n_most_common": ('INT', {'description': "threshold of 'B' in top N most common quality for guessing Illumina 1.5. (default 2) (default 0.1)", 'default': ''}),
                "to": ('STRING', {'description': 'target quality encoding', 'default': 'Sanger'}),
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
