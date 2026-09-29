"""``seqfu grep``: Print sequences selected if they match patterns or contain oligonucleotides.

Generated from the tool's own --help output in the pinned seqfu seqfu 1.28.0 image.
Help page SHA-256: 261b1185a5c6a234f7977a3e5428d56892f4086a915c89aa5edf4ae2a4e2ef16

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import SeqfuBase


class SeqfuGrepNode(SeqfuBase):
    """Print sequences selected if they match patterns or contain oligonucleotides"""

    NODE_ID = 'seqfu_grep'
    DISPLAY_NAME = 'seqfu grep'
    SUBCOMMAND = 'grep'
    DESCRIPTION = 'Print sequences selected if they match patterns or contain oligonucleotides'
    SEARCH_ALIASES = ['seqfu', 'grep']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqfu_grep.out',)
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
                "name": ('STRING', {'description': 'String required inside the sequence name (see -f)', 'default': ''}),
                "regex": ('STRING', {'description': 'Pattern to be matched in sequence name', 'default': ''}),
                "comment": ('BOOLEAN', {'description': 'Also search -n and -r in the comment', 'default': False}),
                "full": ('BOOLEAN', {'description': 'The string or pattern covers the whole name (mainly used without -c)', 'default': False}),
                "word": ('BOOLEAN', {'description': 'The string or pattern is a whole word', 'default': False}),
                "ignore_case": ('BOOLEAN', {'description': 'Ignore case when matching names (is already enabled with regexes)', 'default': False}),
                "oligo": ('STRING', {'description': 'Oligonucleotide required in the sequence, using ambiguous bases and reverse complement', 'default': ''}),
                "append_pos": ('BOOLEAN', {'description': 'Append matching positions to the sequence comment', 'default': False}),
                "max_mismatches": ('INT', {'description': 'Maximum mismatches allowed', 'default': 0}),
                "min_matches": ('INT', {'description': 'Minimum number of matches', 'default': 0}),
                "invert_match": ('BOOLEAN', {'description': 'Invert match (print sequences that do not match)', 'default': False}),
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
