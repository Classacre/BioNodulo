"""``vcfprimers ``: For each VCF record, extract the flanking sequences, and write them to stdout as.

Generated from the tool's own --help output in the pinned vcfprimers 1.0.15 image.
Help page SHA-256: dfd43f14f4e38603ba40eb8a288d5c709efc49d6da00424d53c793673c63a846

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibVcfprimersNode(VcflibBase):
    """For each VCF record, extract the flanking sequences, and write them to stdout as FASTA"""

    NODE_ID = 'vcflib_vcfprimers'
    DISPLAY_NAME = 'vcfprimers'
    DESCRIPTION = 'For each VCF record, extract the flanking sequences, and write them to stdout as FASTA'
    SEARCH_ALIASES = ['vcfprimers']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_vcfprimers.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['vcfprimers']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),

            },
            "optional": {
                "fasta_reference": ('STRING', {'description': 'reference file to use to obtain primer sequences', 'default': ''}),
                "primer_length": ('STRING', {'description': 'The length of the primer sequences on each side of the variant', 'default': ''}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['vcfprimers']
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
