"""``unikmer filter``: Filter out low-complexity k-mers (experimental).

Generated from the tool's own --help output in the pinned unikmer 0.20.0 image.
Help page SHA-256: be1aef79cb8d5767d3f2f97f3e2964a74428531d8d5c05a472fb5c00ccea175f

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import UnikmerBase


class UnikmerFilterNode(UnikmerBase):
    """Filter out low-complexity k-mers (experimental)"""

    NODE_ID = 'unikmer_filter'
    DISPLAY_NAME = 'unikmer filter'
    SUBCOMMAND = 'filter'
    DESCRIPTION = 'Filter out low-complexity k-mers (experimental)'
    SEARCH_ALIASES = ['unikmer', 'filter']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('unikmer_filter.out',)
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
                "invert": ('BOOLEAN', {'description': 'invert result, i.e., output low-complexity k-mers', 'default': False}),
                "penalty_d": ('INT', {'description': 'penalty for different bases', 'default': 1}),
                "penalty_s": ('INT', {'description': 'penalty for successive bases', 'default': 3}),
                "threshold": ('INT', {'description': 'penalty threshold for filter, higher is stricter', 'default': 15}),
                "window": ('INT', {'description': 'window size for checking penalty', 'default': 7}),
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
