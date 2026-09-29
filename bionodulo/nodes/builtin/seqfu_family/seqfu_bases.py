"""``seqfu bases``: Print the DNA bases, and %GC content, in the input files.

Generated from the tool's own --help output in the pinned seqfu seqfu 1.28.0 image.
Help page SHA-256: 71142cbacb01899876b2cdd029f4ec568b7c1ddf64a6ea77d2588c70838df85f

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import SeqfuBase


class SeqfuBasesNode(SeqfuBase):
    """Print the DNA bases, and %GC content, in the input files"""

    NODE_ID = 'seqfu_bases'
    DISPLAY_NAME = 'seqfu bases'
    SUBCOMMAND = 'bases'
    DESCRIPTION = 'Print the DNA bases, and %GC content, in the input files'
    SEARCH_ALIASES = ['seqfu', 'bases']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqfu_bases.out',)
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
                "raw_counts": ('BOOLEAN', {'description': 'Print counts and not ratios', 'default': False}),
                "thousands": ('BOOLEAN', {'description': 'Print thousands separator', 'default': False}),
                "abspath": ('BOOLEAN', {'description': 'Print absolute path', 'default': False}),
                "basename": ('BOOLEAN', {'description': 'Print the basename of the file', 'default': False}),
                "nice": ('BOOLEAN', {'description': 'Print terminal table', 'default': False}),
                "digits": ('INT', {'description': 'Number of digits to print', 'default': 2}),
                "header": ('BOOLEAN', {'description': 'Print header', 'default': False}),
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
