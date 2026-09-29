"""``unikmer encode``: Encode plain k-mer texts to integers.

Generated from the tool's own --help output in the pinned unikmer 0.20.0 image.
Help page SHA-256: eccef11a06d9997d861ae97c770060e9bf4745ad3c1c3560429e269b65cb5714

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import UnikmerBase


class UnikmerEncodeNode(UnikmerBase):
    """Encode plain k-mer texts to integers"""

    NODE_ID = 'unikmer_encode'
    DISPLAY_NAME = 'unikmer encode'
    SUBCOMMAND = 'encode'
    DESCRIPTION = 'Encode plain k-mer texts to integers'
    SEARCH_ALIASES = ['unikmer', 'encode']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('unikmer_encode.out',)
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
                "all": ('BOOLEAN', {'description': 'output all data: orginial k-mer, parsed k-mer, encoded integer, encode bits', 'default': False}),
                "canonical": ('BOOLEAN', {'description': 'keep the canonical k-mers', 'default': False}),
                "hash": ('BOOLEAN', {'description': 'save hash of k-mer, automatically on for k>32', 'default': False}),
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
