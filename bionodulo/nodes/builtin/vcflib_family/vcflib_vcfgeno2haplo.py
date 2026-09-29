"""``vcfgeno2haplo ``: Convert genotype-based phased alleles within --window-size into haplotype allele.

Generated from the tool's own --help output in the pinned vcfgeno2haplo 1.0.15 image.
Help page SHA-256: c59ede6b40c751fcf88f9fc2cfe6e4f1a25dcae0f11bb0944d8e0f44a802fa20

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibVcfgeno2haploNode(VcflibBase):
    """Convert genotype-based phased alleles within --window-size into haplotype alleles."""

    NODE_ID = 'vcflib_vcfgeno2haplo'
    DISPLAY_NAME = 'vcfgeno2haplo'
    DESCRIPTION = 'Convert genotype-based phased alleles within --window-size into haplotype alleles.'
    SEARCH_ALIASES = ['vcfgeno2haplo']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_vcfgeno2haplo.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['vcfgeno2haplo']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),

            },
            "optional": {
                "reference": ('STRING', {'description': 'FASTA reference file', 'default': ''}),
                "window_size": ('STRING', {'description': 'Merge variants at most this many bp apart', 'default': 'default 30'}),
                "only_variants": ('BOOLEAN', {'description': 'Don\'t output the entire haplotype, just concatenate REF/ALT strings (delimited by ":")', 'default': False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['vcfgeno2haplo']
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
