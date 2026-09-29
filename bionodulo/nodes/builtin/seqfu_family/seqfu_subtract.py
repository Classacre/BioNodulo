"""``seqfu subtract``: Print sequences from <file1> that are not present in <file2>..

Generated from the tool's own --help output in the pinned seqfu seqfu 1.28.0 image.
Help page SHA-256: 52c22c5980c9d4dc313f748cbafcbfc03f7fc14053cc39f2e62cd0ed04308a67

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import SeqfuBase


class SeqfuSubtractNode(SeqfuBase):
    """Print sequences from <file1> that are not present in <file2>."""

    NODE_ID = 'seqfu_subtract'
    DISPLAY_NAME = 'seqfu subtract'
    SUBCOMMAND = 'subtract'
    DESCRIPTION = 'Print sequences from <file1> that are not present in <file2>.'
    SEARCH_ALIASES = ['seqfu', 'subtract']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqfu_subtract.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://telatin.github.io/seqfu2/'
    REQUIRED_EXECUTABLES = ['seqfu']
    REQUIRED_CONDA_PACKAGES = ['seqfu']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'file1': ('FILE', {"description": "Input file1"}),
                'file2': ('FILE', {"description": "Input file2"}),

            },
            "optional": {
                "by_seq": ('BOOLEAN', {'description': 'Match by sequence content instead of name', 'default': False}),
                "relaxed": ('BOOLEAN', {'description': "Don't error if sequences in <file2> are absent from <file1>", 'default': False}),
                "strip_comment": ('BOOLEAN', {'description': 'Ignore name suffix after first space when matching', 'default': False}),
                "strip_pair": ('BOOLEAN', {'description': 'Ignore /1 or /2 pair suffixes in names when matching', 'default': False}),
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
                if name in ('file1', 'file2'):
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
        command.append(str(inputs.get('file1', "")))
        command.append(str(inputs.get('file2', "")))
        return command
