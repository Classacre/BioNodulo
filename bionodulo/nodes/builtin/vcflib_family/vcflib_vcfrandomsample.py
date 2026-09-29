"""``vcfrandomsample ``: Randomly sample sites from an input VCF file, which may be provided as stdin..

Generated from the tool's own --help output in the pinned vcfrandomsample 1.0.15 image.
Help page SHA-256: 5ce55a6e6cb4e1193d360a120a72534a2ed499799d78e549dfa7c028f41408d2

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibVcfrandomsampleNode(VcflibBase):
    """Randomly sample sites from an input VCF file, which may be provided as stdin."""

    NODE_ID = 'vcflib_vcfrandomsample'
    DISPLAY_NAME = 'vcfrandomsample'
    DESCRIPTION = 'Randomly sample sites from an input VCF file, which may be provided as stdin.'
    SEARCH_ALIASES = ['vcfrandomsample']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_vcfrandomsample.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['vcfrandomsample']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),

            },
            "optional": {
                "rate": ('STRING', {'description': 'base sampling probability per locus', 'default': ''}),
                "scale_by": ('STRING', {'description': 'scale sampling likelihood by this Float info field', 'default': ''}),
                "random_seed": ('STRING', {'description': 'use this random seed (by default read from /dev/random)', 'default': ''}),
                "pseudorandom_seed": ('STRING', {'description': 'use a pseudorandom seed (by default read from /dev/random)', 'default': ''}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['vcfrandomsample']
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
