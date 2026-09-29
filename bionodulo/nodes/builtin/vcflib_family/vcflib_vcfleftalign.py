"""``vcfleftalign ``: Left-align indels and complex variants in the input using a pairwise.

Generated from the tool's own --help output in the pinned vcfleftalign 1.0.15 image.
Help page SHA-256: 5e0e956dc0a7920dfb5cc6dd0256e6f547e0d6e4341f9bfd9003f201b8748a70

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibVcfleftalignNode(VcflibBase):
    """Left-align indels and complex variants in the input using a pairwise"""

    NODE_ID = 'vcflib_vcfleftalign'
    DISPLAY_NAME = 'vcfleftalign'
    DESCRIPTION = 'Left-align indels and complex variants in the input using a pairwise'
    SEARCH_ALIASES = ['vcfleftalign']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_vcfleftalign.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['vcfleftalign']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),

            },
            "optional": {
                "reference": ('STRING', {'description': 'Use this reference as a basis for realignment.', 'default': ''}),
                "window": ('STRING', {'description': 'Use a window of this many bp when left aligning', 'default': '150'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['vcfleftalign']
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
