"""``seqkit split``: split sequences into files by name ID, subsequence of given region,.

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: f835183a935d0f186ecd8e35ffbbd8ce26b7dd849142b97f1a4d82355b9c6840

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitSplitNode(SeqkitBase):
    """split sequences into files by name ID, subsequence of given region,"""

    NODE_ID = 'seqkit_split'
    DISPLAY_NAME = 'seqkit split'
    SUBCOMMAND = 'split'
    DESCRIPTION = 'split sequences into files by name ID, subsequence of given region,'
    SEARCH_ALIASES = ['seqkit', 'split']
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("output_dir",)
    OUTPUT_FILENAMES = ()
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
                "by_id": ('BOOLEAN', {'description': 'split squences according to sequence ID', 'default': False}),
                "by_id_prefix": ('STRING', {'description': 'file prefix for --by-id', 'default': ''}),
                "by_part": ('INT', {'description': 'split sequences into N parts', 'default': ''}),
                "by_part_prefix": ('STRING', {'description': 'file prefix for --by-part', 'default': ''}),
                "by_region": ('STRING', {'description': 'split squences according to subsequence of given region. e.g 1:12 for first 12 bases, -12:-1 for last 12 bases. type "seqkit split -h" for more examples', 'default': ''}),
                "by_region_prefix": ('STRING', {'description': 'file prefix for --by-region', 'default': ''}),
                "by_size": ('INT', {'description': 'split sequences into multi parts with N sequences', 'default': ''}),
                "by_size_prefix": ('STRING', {'description': 'file prefix for --by-size', 'default': ''}),
                "dry_run": ('BOOLEAN', {'description': 'dry run, just print message and no files will be created.', 'default': False}),
                "extension": ('STRING', {'description': 'set output file extension, e.g., ".gz", ".xz", or ".zst"', 'default': ''}),
                "force": ('BOOLEAN', {'description': 'overwrite output directory', 'default': False}),
                "ignore_case": ('BOOLEAN', {'description': 'ignore case when using -i/--by-id', 'default': False}),
                "keep_temp": ('BOOLEAN', {'description': 'keep temporary FASTA and .fai file when using 2-pass mode', 'default': False}),
                "out_prefix": ('STRING', {'description': 'file prefix (it overrides --by-*-prefix). The placeholder "{read}" is needed for paired-end files.', 'default': ''}),
                "two_pass": ('BOOLEAN', {'description': 'two-pass mode read files twice to lower memory usage. (only for FASTA format)', 'default': False}),
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
        command.extend(['--out-dir', str(output_dir)])
        command.append(str(inputs.get('sequence', "")))
        return command
