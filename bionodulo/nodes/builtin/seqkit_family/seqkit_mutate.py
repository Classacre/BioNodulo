"""``seqkit mutate``: edit sequence (point mutation, insertion, deletion).

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: 1b3fc2d7d360e0f0212b9ff46d495d61ac1aa07300877aed86793a016c1611c6

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitMutateNode(SeqkitBase):
    """edit sequence (point mutation, insertion, deletion)"""

    NODE_ID = 'seqkit_mutate'
    DISPLAY_NAME = 'seqkit mutate'
    SUBCOMMAND = 'mutate'
    DESCRIPTION = 'edit sequence (point mutation, insertion, deletion)'
    SEARCH_ALIASES = ['seqkit', 'mutate']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqkit_mutate.out',)
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
                "by_name": ('BOOLEAN', {'description': '[match seqs to mutate] match by full name instead of just id', 'default': False}),
                "deletion": ('STRING', {'description': 'deletion mutation: deleting subsequence in a range. e.g., -d 1:2 for deleting leading two bases, -d -3:-1 for removing last 3 bases', 'default': ''}),
                "ignore_case": ('BOOLEAN', {'description': '[match seqs to mutate] ignore case of search pattern', 'default': False}),
                "insertion": ('STRING', {'description': 'insertion mutation: inserting bases behind of given position, e.g., -i 0:ACGT for inserting ACGT at the beginning, -1:* for add * to the end', 'default': ''}),
                "invert_match": ('BOOLEAN', {'description': '[match seqs to mutate] invert the sense of matching, to select non-matching records', 'default': False}),
                "pattern": ('STRING', {'description': '[match seqs to mutate] search pattern .Multiple values supported: comma-separated (e.g., -p "p1,p2") OR use -p multiple times (e.g., -p p1 -p p2). Make sure to quote literal commas, e.g. in regex patt', 'default': ''}),
                "pattern_file": ('STRING', {'description': '[match seqs to mutate] pattern file (one record per line)', 'default': ''}),
                "point": ('STRING', {'description': 'point mutation: changing base at given position. e.g., -p 2:C for setting 2nd base as C, -p -1:A for change last base as A', 'default': ''}),
                "use_regexp": ('BOOLEAN', {'description': '[match seqs to mutate] search patterns are regular expression', 'default': False}),
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
