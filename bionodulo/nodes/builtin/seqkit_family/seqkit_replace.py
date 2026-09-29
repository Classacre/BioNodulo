"""``seqkit replace``: replace name/sequence by regular expression..

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: 59af8363efa0e6a809f4886f6befa4e16a3595055d1eda44577b386e0ad78d1c

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitReplaceNode(SeqkitBase):
    """replace name/sequence by regular expression."""

    NODE_ID = 'seqkit_replace'
    DISPLAY_NAME = 'seqkit replace'
    SUBCOMMAND = 'replace'
    DESCRIPTION = 'replace name/sequence by regular expression.'
    SEARCH_ALIASES = ['seqkit', 'replace']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqkit_replace.out',)
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/seqkit/'
    REQUIRED_EXECUTABLES = ['seqkit']
    REQUIRED_CONDA_PACKAGES = ['seqkit']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ("FILE", {"description": 'Input FASTA/FASTQ file'}),
                "pattern": ('STRING', {'description': 'search regular expression', 'default': ''}),
            },
            "optional": {
                "by_seq": ('BOOLEAN', {'description': 'replace seq (only FASTA)', 'default': False}),
                "f_by_name": ('BOOLEAN', {'description': '[target filter] match by full name instead of just ID', 'default': False}),
                "f_by_seq": ('BOOLEAN', {'description': '[target filter] search subseq on seq, both positive and negative strand are searched', 'default': False}),
                "f_ignore_case": ('BOOLEAN', {'description': '[target filter] ignore case', 'default': False}),
                "f_invert_match": ('BOOLEAN', {'description': '[target filter] invert the sense of matching, to select non-matching records', 'default': False}),
                "f_only_positive_strand": ('BOOLEAN', {'description': '[target filter] only search on positive strand', 'default': False}),
                "f_pattern": ('STRING', {'description': '[target filter] search pattern (multiple values supported. Attention: use double quotation marks for patterns containing comma, e.g., -p \'"A{2,}"\')', 'default': ''}),
                "f_pattern_file": ('STRING', {'description': '[target filter] pattern file (one record per line)', 'default': ''}),
                "f_use_regexp": ('BOOLEAN', {'description': '[target filter] patterns are regular expression', 'default': False}),
                "ignore_case": ('BOOLEAN', {'description': 'ignore case', 'default': False}),
                "keep_key": ('BOOLEAN', {'description': 'keep the key as value when no value found for the key (only for sequence name)', 'default': False}),
                "keep_untouch": ('BOOLEAN', {'description': 'do not change anything when no value found for the key (only for sequence name)', 'default': False}),
                "key_capt_idx": ('INT', {'description': 'capture variable index of key (1-based)', 'default': 1}),
                "key_miss_repl": ('STRING', {'description': 'replacement for key with no corresponding value', 'default': ''}),
                "kv_file": ('STRING', {'description': 'tab-delimited key-value file for replacing key with value when using "{kv}" in -r (--replacement) (only for sequence name)', 'default': ''}),
                "nr_width": ('INT', {'description': 'minimum width for {nr} in flag -r/--replacement. e.g., formatting "1" to "001" by --nr-width 3 (default 1)', 'default': ''}),
                "replacement": ('STRING', {'description': 'replacement. supporting capture variables.  e.g. $1 represents the text of the first submatch (use ${1} instead of $1 when {kv} given!). ATTENTION: for *nix OS, use SINGLE quote NOT double quotes or u', 'default': ''}),
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
