"""``unikmer tsplit``: Split k-mers according to taxid.

Generated from the tool's own --help output in the pinned unikmer 0.20.0 image.
Help page SHA-256: 6757cf6aa5e731b3d29496cbcde3b272db51e558dc74a6cf4bd451d2a7d25d97

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import UnikmerBase


class UnikmerTsplitNode(UnikmerBase):
    """Split k-mers according to taxid"""

    NODE_ID = 'unikmer_tsplit'
    DISPLAY_NAME = 'unikmer tsplit'
    SUBCOMMAND = 'tsplit'
    DESCRIPTION = 'Split k-mers according to taxid'
    SEARCH_ALIASES = ['unikmer', 'tsplit']
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
                "force": ('BOOLEAN', {'description': 'overwrite output directory', 'default': False}),
                "out_prefix": ('STRING', {'description': 'out file prefix', 'default': 'tsplit'}),
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
