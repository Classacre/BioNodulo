"""``abba-baba ``: abba-baba calculates the tree pattern for four indviduals. This tool assumes ref.

Generated from the tool's own --help output in the pinned abba-baba 1.0.15 image.
Help page SHA-256: 10259e7c8a6652999c309b8e05a6d1237aea801fcb65853fe118d4431fc5b38f

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibAbbaBabaNode(VcflibBase):
    """abba-baba calculates the tree pattern for four indviduals. This tool assumes reference is ancestral and ignores non abba-baba sites."""

    NODE_ID = 'vcflib_abba_baba'
    DISPLAY_NAME = 'abba-baba'
    DESCRIPTION = 'abba-baba calculates the tree pattern for four indviduals. This tool assumes reference is ancestral and ignores non abba-baba sites.'
    SEARCH_ALIASES = ['abba-baba']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_abba_baba.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['abba-baba']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),
                "tree": ('STRING', {'description': 'a zero based comma separated list of target individuals corrisponding to VCF columns', 'default': ''}),
                "type": ('STRING', {'description': 'genotype likelihood format ; genotypes: GP,GL or PL;', 'default': ''}),
            },
            "optional": {

            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['abba-baba']
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
