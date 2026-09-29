"""``vcfld ``: Compute LD.

Generated from the tool's own --help output in the pinned vcfld 1.0.15 image.
Help page SHA-256: 8c743f0402cc2afa07fcb81ff13ba8d2f6d5e3c2d462c6e929092cc04722ab98

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibVcfldNode(VcflibBase):
    """Compute LD"""

    NODE_ID = 'vcflib_vcfld'
    DISPLAY_NAME = 'vcfld'
    DESCRIPTION = 'Compute LD'
    SEARCH_ALIASES = ['vcfld']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_vcfld.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['vcfld']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),
                "target": ('STRING', {'description': 'argument: a zero base comma separated list of target individuals corresponding to VCF columns', 'default': ''}),
                "background": ('STRING', {'description': 'argument: a zero base comma separated list of background individuals corresponding to VCF columns', 'default': ''}),
                "type": ('STRING', {'description': 'argument: type of genotype likelihood: PL, GL or GP', 'default': ''}),
            },
            "optional": {
                "window": ('STRING', {'description': 'argument: window size to average LD; default is 1000', 'default': ''}),
                "external": ('STRING', {'description': 'switch: population to calculate LD expectation; default is target', 'default': ''}),
                "derived": ('STRING', {'description': 'switch: which haplotype to count "00" vs "11"; default "00",', 'default': ''}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['vcfld']
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
