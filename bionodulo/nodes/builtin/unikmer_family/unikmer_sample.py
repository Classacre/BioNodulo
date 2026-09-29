"""``unikmer sample``: Sample k-mers from binary files..

Generated from the tool's own --help output in the pinned unikmer 0.20.0 image.
Help page SHA-256: 663586a6a5b4a244252841ce264b771673d43ed61a53c58ff44ce76096d5e22f

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import UnikmerBase


class UnikmerSampleNode(UnikmerBase):
    """Sample k-mers from binary files."""

    NODE_ID = 'unikmer_sample'
    DISPLAY_NAME = 'unikmer sample'
    SUBCOMMAND = 'sample'
    DESCRIPTION = 'Sample k-mers from binary files.'
    SEARCH_ALIASES = ['unikmer', 'sample']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('unikmer_sample.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/unikmer/'
    REQUIRED_EXECUTABLES = ['unikmer']
    REQUIRED_CONDA_PACKAGES = ['unikmer']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input k-mer file (.unik) or FASTA/Q file'}),

            },
            "optional": {
                "start": ('INT', {'description': 'start location', 'default': 1}),
                "window": ('INT', {'description': 'window size', 'default': 1}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['unikmer', cls.SUBCOMMAND]
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
        command.extend(['--out-prefix', "-"])
        command.append(str(inputs.get('input', "")))
        return command
