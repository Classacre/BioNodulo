"""``vcfremoveaberrantgenotypes ``: strips samples which are homozygous but have observations implying heterozygosit.

Generated from the tool's own --help output in the pinned vcfremoveaberrantgenotypes 1.0.15 image.
Help page SHA-256: dca1c3ad0b96ea02f97494dccdcc65e971b1d2a0a2075dc4e5c3ed82574dbec8

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibVcfremoveaberrantgenotypesNode(VcflibBase):
    """strips samples which are homozygous but have observations implying heterozygosity."""

    NODE_ID = 'vcflib_vcfremoveaberrantgenotypes'
    DISPLAY_NAME = 'vcfremoveaberrantgenotypes'
    DESCRIPTION = 'strips samples which are homozygous but have observations implying heterozygosity.'
    SEARCH_ALIASES = ['vcfremoveaberrantgenotypes']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_vcfremoveaberrantgenotypes.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['vcfremoveaberrantgenotypes']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),

            },
            "optional": {

            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['vcfremoveaberrantgenotypes']
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
