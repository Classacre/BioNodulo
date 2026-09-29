"""``smoother ``: smoothes is a method for window smoothing many of the GPAT++ formats..

Generated from the tool's own --help output in the pinned smoother 1.0.15 image.
Help page SHA-256: a09aec7c2c22bdb2b36dcba381b01dfa9734da55d5654e84c29dae4f5acb99af

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibSmootherNode(VcflibBase):
    """smoothes is a method for window smoothing many of the GPAT++ formats."""

    NODE_ID = 'vcflib_smoother'
    DISPLAY_NAME = 'smoother'
    DESCRIPTION = 'smoothes is a method for window smoothing many of the GPAT++ formats.'
    SEARCH_ALIASES = ['smoother']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_smoother.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['smoother']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),
                "format": ('STRING', {'description': 'argument: format of input file, case sensitive', 'default': ''}),
            },
            "optional": {
                "window": ('STRING', {'description': 'argument: size of genomic window in base pairs', 'default': 'default 5000'}),
                "step": ('STRING', {'description': 'argument: window step size in base pairs', 'default': 'default 1000'}),
                "truncate": ('STRING', {'description': 'flag    : end last window at last position', 'default': 'zero based'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['smoother']
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
        command.extend(['--file', str(inputs.get('input', ""))])
        return command
