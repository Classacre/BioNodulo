"""``unikmer concat``: Concatenate multiple binary files without removing duplicates.

Generated from the tool's own --help output in the pinned unikmer 0.20.0 image.
Help page SHA-256: 3b96f8a1ae9d9b23b182df38244df9871569be337810e6853f8bbe0bc86bc4e7

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import UnikmerBase


class UnikmerConcatNode(UnikmerBase):
    """Concatenate multiple binary files without removing duplicates"""

    NODE_ID = 'unikmer_concat'
    DISPLAY_NAME = 'unikmer concat'
    SUBCOMMAND = 'concat'
    DESCRIPTION = 'Concatenate multiple binary files without removing duplicates'
    SEARCH_ALIASES = ['unikmer', 'concat']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('unikmer_concat.out',)
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
                "number": ('INT', {'description': 'number of k-mers', 'default': -1}),
                "sorted": ('BOOLEAN', {'description': 'input k-mers are sorted', 'default': False}),
                "taxid": ('STRING', {'description': 'global taxid', 'default': ''}),
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
