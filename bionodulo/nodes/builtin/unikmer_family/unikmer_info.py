"""``unikmer info``: Information of binary files.

Generated from the tool's own --help output in the pinned unikmer 0.20.0 image.
Help page SHA-256: 86f41b24a9993a3f350af230d3d820fe245e22fdccb4ae6b63ac12f9543f6f12

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import UnikmerBase


class UnikmerInfoNode(UnikmerBase):
    """Information of binary files"""

    NODE_ID = 'unikmer_info'
    DISPLAY_NAME = 'unikmer info'
    SUBCOMMAND = 'info'
    DESCRIPTION = 'Information of binary files'
    SEARCH_ALIASES = ['unikmer', 'info']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('unikmer_info.out',)
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
                "all": ('BOOLEAN', {'description': 'all information, including number of k-mers', 'default': False}),
                "basename": ('BOOLEAN', {'description': 'only output basename of files', 'default': False}),
                "skip_err": ('BOOLEAN', {'description': 'skip error, only show warning message', 'default': False}),
                "symbol_false": ('STRING', {'description': 'smybol for false', 'default': '✕'}),
                "symbol_true": ('STRING', {'description': 'smybol for true', 'default': '✓'}),
                "tabular": ('BOOLEAN', {'description': 'output in machine-friendly tabular format', 'default': False}),
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
        command.extend(['--out-file', str(output_dir / cls.OUTPUT_FILENAMES[0])])
        command.append(str(inputs.get('input', "")))
        return command
