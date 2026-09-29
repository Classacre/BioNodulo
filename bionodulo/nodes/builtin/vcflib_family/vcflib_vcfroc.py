"""``vcfroc ``: Generates a pseudo-ROC curve using sensitivity and specificity estimated against.

Generated from the tool's own --help output in the pinned vcfroc 1.0.15 image.
Help page SHA-256: fcfceca95cfa98ab3f75783d7767a493572ebe0faf81f4a687e92c527bdee8e6

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibVcfrocNode(VcflibBase):
    """Generates a pseudo-ROC curve using sensitivity and specificity estimated against"""

    NODE_ID = 'vcflib_vcfroc'
    DISPLAY_NAME = 'vcfroc'
    DESCRIPTION = 'Generates a pseudo-ROC curve using sensitivity and specificity estimated against'
    SEARCH_ALIASES = ['vcfroc']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_vcfroc.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['vcfroc']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),

            },
            "optional": {
                "truth_vcf": ('STRING', {'description': 'use this VCF as ground truth for ROC generation', 'default': ''}),
                "window_size": ('STRING', {'description': 'compare records up to this many bp away', 'default': 'default 30'}),
                "complex": ('STRING', {'description': "directly compare complex alleles, don't parse into primitives", 'default': ''}),
                "reference": ('STRING', {'description': 'FASTA reference file', 'default': ''}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['vcfroc']
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
