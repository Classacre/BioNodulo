"""``seqfu cat``: Concatenate multiple FASTA or FASTQ files..

Generated from the tool's own --help output in the pinned seqfu seqfu 1.28.0 image.
Help page SHA-256: 847121e121d3a7783fb6f28d775c773aeb9d109bfdc3ae1df803905eaccc40ca

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import SeqfuBase


class SeqfuCatNode(SeqfuBase):
    """Concatenate multiple FASTA or FASTQ files."""

    NODE_ID = 'seqfu_cat'
    DISPLAY_NAME = 'seqfu cat'
    SUBCOMMAND = 'cat'
    DESCRIPTION = 'Concatenate multiple FASTA or FASTQ files.'
    SEARCH_ALIASES = ['seqfu', 'cat']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqfu_cat.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://telatin.github.io/seqfu2/'
    REQUIRED_EXECUTABLES = ['seqfu']
    REQUIRED_CONDA_PACKAGES = ['seqfu']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input sequence file'}),

            },
            "optional": {
                "skip": ('STRING', {'description': 'Print one sequence every STEP', 'default': '0'}),
                "skip_first": ('INT', {'description': 'Skip the first INT records', 'default': -1}),
                "jump_to": ('STRING', {'description': 'Start from the record after the one named STR (overrides --skip-first)', 'default': ''}),
                "print_last": ('BOOLEAN', {'description': 'Print the name of the last sequence to STDERR (Last:NAME)', 'default': False}),
                "prefix": ('STRING', {'description': 'Rename sequences with prefix + incremental number', 'default': ''}),
                "strip_name": ('BOOLEAN', {'description': 'Remove the original sequence name', 'default': False}),
                "append": ('STRING', {'description': 'Append this string to the sequence name', 'default': ''}),
                "sep": ('STRING', {'description': 'Sequence name fields separator', 'default': '_'}),
                "basename": ('BOOLEAN', {'description': 'Prepend file basename to the sequence name (before prefix)', 'default': False}),
                "split": ('STRING', {'description': 'Split basename at this char', 'default': '.'}),
                "part": ('INT', {'description': 'After splitting the basename, take this part', 'default': 1}),
                "basename_sep": ('STRING', {'description': 'Separate basename from the rest with this', 'default': '_'}),
                "zero_pad": ('INT', {'description': 'Zero pad the counter to INT digits', 'default': 0}),
                "strip_comments": ('BOOLEAN', {'description': 'Remove original sequence comments', 'default': False}),
                "comment_sep": ('STRING', {'description': 'Comment separator', 'default': ''}),
                "add_len": ('BOOLEAN', {'description': "Add 'len=LENGTH' to the comments", 'default': False}),
                "add_initial_len": ('BOOLEAN', {'description': "Add 'original_len=LENGTH' to the comments", 'default': False}),
                "add_gc": ('BOOLEAN', {'description': "Add 'gc=%GC' to the comments", 'default': False}),
                "add_initial_gc": ('BOOLEAN', {'description': "Add 'original_gc=%GC' to the comments", 'default': False}),
                "add_name": ('BOOLEAN', {'description': "Add 'original_name=INITIAL_NAME' to the comments", 'default': False}),
                "add_ee": ('BOOLEAN', {'description': "Add 'ee=EXPECTED_ERROR' to the comments", 'default': False}),
                "add_initial_ee": ('BOOLEAN', {'description': "Add 'original_ee=EXPECTED_ERROR' to the comments", 'default': False}),
                "max_ns": ('INT', {'description': 'Discard sequences with more than INT Ns', 'default': -1}),
                "min_len": ('INT', {'description': 'Discard sequences shorter than INT', 'default': 1}),
                "max_len": ('INT', {'description': 'Discard sequences longer than INT, 0 to ignore', 'default': 0}),
                "max_ee": ('FLOAT', {'description': 'Discard sequences with higher than FLOAT expected error', 'default': -1.0}),
                "trim_front": ('INT', {'description': 'Trim INT base from the start of the sequence', 'default': 0}),
                "trim_tail": ('INT', {'description': 'Trim INT base from the end of the sequence', 'default': 0}),
                "truncate": ('INT', {'description': 'Keep only the first INT bases, 0 to ignore Negative values to print the last INT bases', 'default': 0}),
                "max_bp": ('INT', {'description': 'Stop printing after INT bases', 'default': 0}),
                "fasta": ('BOOLEAN', {'description': 'Force FASTA output', 'default': False}),
                "fastq": ('BOOLEAN', {'description': 'Force FASTQ output', 'default': False}),
                "report": ('STRING', {'description': 'Save a report to FILE (original name, new name)', 'default': ''}),
                "list": ('BOOLEAN', {'description': 'Output a list of sequence names', 'default': False}),
                "long": ('BOOLEAN', {'description': 'Output a list, with sequence name and comments', 'default': False}),
                "anvio": ('BOOLEAN', {'description': 'Output in Anvio format (-p c_ -s -z --zeropad 12 --report rename_report.txt)', 'default': False}),
                "fastq_qual": ('INT', {'description': 'FASTQ default quality', 'default': 33}),
                "debug": ('BOOLEAN', {'description': 'Debug output', 'default': False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['seqfu', cls.SUBCOMMAND]
        # Required flags must be rendered too. Iterating only "optional" silently
        # dropped every empirically-required flag (csvtk mutate --name and friends).
        declared_types = cls.INPUT_TYPES()
        for category in ("required", "optional"):
            for name, spec in declared_types.get(category, {}).items():
                if name in ('input',):
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
        command.append(str(inputs.get('input', "")))
        return command
