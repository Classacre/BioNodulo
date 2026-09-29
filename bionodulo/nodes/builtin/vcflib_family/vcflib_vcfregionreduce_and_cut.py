"""``vcfregionreduce_and_cut ``: Generates `basename directory`.vcf.gz and `basename directory`.sites.vcf.gz.

Generated from the tool's own --help output in the pinned vcfregionreduce_and_cut 1.0.15 image.
Help page SHA-256: 3d15398b5d6e844b5fb0956b8b5e22ce34240a0b53034b251fc48b31a4ecc29a

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibVcfregionreduceAndCutNode(VcflibBase):
    """Generates `basename directory`.vcf.gz and `basename directory`.sites.vcf.gz"""

    NODE_ID = 'vcflib_vcfregionreduce_and_cut'
    DISPLAY_NAME = 'vcfregionreduce_and_cut'
    DESCRIPTION = 'Generates `basename directory`.vcf.gz and `basename directory`.sites.vcf.gz'
    SEARCH_ALIASES = ['vcfregionreduce_and_cut']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_vcfregionreduce_and_cut.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['vcfregionreduce_and_cut']
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
        command = ['vcfregionreduce_and_cut']
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
