"""``seqkit seq``: transform sequences (extract ID, filter by length, remove gaps, reverse compleme.

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: 860397d80d92fa7f47ac7bf50e59efe5277e8588dcdc7819a58f4c3f5b072420

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitSeqNode(SeqkitBase):
    """transform sequences (extract ID, filter by length, remove gaps, reverse complement...)"""

    NODE_ID = 'seqkit_seq'
    DISPLAY_NAME = 'seqkit seq'
    SUBCOMMAND = 'seq'
    DESCRIPTION = 'transform sequences (extract ID, filter by length, remove gaps, reverse complement...)'
    SEARCH_ALIASES = ['seqkit', 'seq']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqkit_seq.out',)
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
                "color": ('BOOLEAN', {'description': 'colorize sequences - to be piped into "less -R"', 'default': False}),
                "complement": ('BOOLEAN', {'description': "complement sequence, flag '-v' is recommended to switch on", 'default': False}),
                "dna2rna": ('BOOLEAN', {'description': 'DNA to RNA', 'default': False}),
                "f_by_name": ('BOOLEAN', {'description': '[target filter] match by full name instead of just ID', 'default': False}),
                "f_by_seq": ('BOOLEAN', {'description': '[target filter] search subseq on seq, both positive and negative strand are searched', 'default': False}),
                "f_ignore_case": ('BOOLEAN', {'description': '[target filter] ignore case', 'default': False}),
                "f_invert_match": ('BOOLEAN', {'description': '[target filter] invert the sense of matching, to select non-matching records', 'default': False}),
                "f_only_positive_strand": ('BOOLEAN', {'description': '[target filter] only search on positive strand', 'default': False}),
                "f_pattern": ('STRING', {'description': '[target filter] search pattern (multiple values supported. Attention: use double quotation marks for patterns containing comma, e.g., -p \'"A{2,}"\')', 'default': ''}),
                "f_pattern_file": ('STRING', {'description': '[target filter] pattern file (one record per line)', 'default': ''}),
                "f_use_regexp": ('BOOLEAN', {'description': '[target filter] patterns are regular expression', 'default': False}),
                "gap_letters": ('STRING', {'description': 'gap letters to be removed with -g/--remove-gaps', 'default': '- \\t.'}),
                "lower_case": ('BOOLEAN', {'description': 'print sequences in lower case', 'default': False}),
                "max_len": ('INT', {'description': 'only print sequences shorter than or equal to the maximum length (-1 for no limit) (default -1)', 'default': ''}),
                "max_qual": ('FLOAT', {'description': 'only print sequences with average quality less than this limit (-1 for no limit) (default -1)', 'default': ''}),
                "min_len": ('INT', {'description': 'only print sequences longer than or equal to the minimum length (-1 for no limit) (default -1)', 'default': ''}),
                "min_qual": ('FLOAT', {'description': 'only print sequences with average quality greater or equal than this limit (-1 for no limit) (default -1)', 'default': ''}),
                "name": ('BOOLEAN', {'description': 'only print names/sequence headers', 'default': False}),
                "only_id": ('BOOLEAN', {'description': 'print IDs instead of full headers', 'default': False}),
                "qual": ('BOOLEAN', {'description': 'only print qualities', 'default': False}),
                "qual_ascii_base": ('INT', {'description': 'ASCII BASE, 33 for Phred+33', 'default': 33}),
                "remove_gaps": ('BOOLEAN', {'description': 'remove gaps letters seft by -G/--gap-letters, e.g., spaces, tabs, and dashes (gaps "-" in aligned sequences)', 'default': False}),
                "reverse": ('BOOLEAN', {'description': 'reverse sequence', 'default': False}),
                "rna2dna": ('BOOLEAN', {'description': 'RNA to DNA', 'default': False}),
                "seq": ('BOOLEAN', {'description': 'only print sequences', 'default': False}),
                "upper_case": ('BOOLEAN', {'description': 'print sequences in upper case', 'default': False}),
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
