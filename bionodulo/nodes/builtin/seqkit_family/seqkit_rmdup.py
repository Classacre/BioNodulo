"""``seqkit rmdup``: remove duplicated sequences by ID/name/sequence.

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: eead3263fbc5faf199c3dccdc68c783f70910cd1dd21795cb50424b4b35fd643

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitRmdupNode(SeqkitBase):
    """remove duplicated sequences by ID/name/sequence"""

    NODE_ID = 'seqkit_rmdup'
    DISPLAY_NAME = 'seqkit rmdup'
    SUBCOMMAND = 'rmdup'
    DESCRIPTION = 'remove duplicated sequences by ID/name/sequence'
    SEARCH_ALIASES = ['seqkit', 'rmdup']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqkit_rmdup.out',)
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
                "by_name": ('BOOLEAN', {'description': 'by full name instead of just id', 'default': False}),
                "by_seq": ('BOOLEAN', {'description': 'by seq', 'default': False}),
                "dup_num_file": ('STRING', {'description': 'file to save numbers and ID lists of duplicated seqs', 'default': ''}),
                "dup_seqs_file": ('STRING', {'description': 'file to save duplicated seqs', 'default': ''}),
                "ignore_case": ('BOOLEAN', {'description': 'ignore case', 'default': False}),
                "only_positive_strand": ('BOOLEAN', {'description': 'only considering positive strand when comparing by sequence', 'default': False}),
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
