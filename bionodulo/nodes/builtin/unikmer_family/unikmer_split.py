"""``unikmer split``: Split k-mers into sorted chunk files.

Generated from the tool's own --help output in the pinned unikmer 0.20.0 image.
Help page SHA-256: e1a0cfb0b4e198bdb18d1b33df8ded7ac094c3028e45bd31f6a52c1eb9a7a694

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import UnikmerBase


class UnikmerSplitNode(UnikmerBase):
    """Split k-mers into sorted chunk files"""

    NODE_ID = 'unikmer_split'
    DISPLAY_NAME = 'unikmer split'
    SUBCOMMAND = 'split'
    DESCRIPTION = 'Split k-mers into sorted chunk files'
    SEARCH_ALIASES = ['unikmer', 'split']
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("output_dir",)
    OUTPUT_FILENAMES = ()
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
                "chunk_size": ('STRING', {'description': 'split input into chunks of N k-mers, supports K/M/G suffix, type "unikmer sort -h" for detail', 'default': ''}),
                "force": ('BOOLEAN', {'description': 'overwrite output directory', 'default': False}),
                "repeated": ('BOOLEAN', {'description': 'split for further printing duplicate k-mers', 'default': False}),
                "unique": ('BOOLEAN', {'description': 'split for further removing duplicate k-mers', 'default': False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
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
        command.extend(['--out-dir', str(output_dir)])
        command.append(str(inputs.get('input', "")))
        return command
