"""``hapLrt ``: HapLRT is a likelihood ratio test for haplotype lengths.  The lengths are modele.

Generated from the tool's own --help output in the pinned hapLrt 1.0.15 image.
Help page SHA-256: e83635d09ed1f08349709bb387327732f21dbf757ce1eb85bf64547970113d78

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibHaplrtNode(VcflibBase):
    """HapLRT is a likelihood ratio test for haplotype lengths.  The lengths are modeled with an exponential distribution."""

    NODE_ID = 'vcflib_haplrt'
    DISPLAY_NAME = 'hapLrt'
    DESCRIPTION = 'HapLRT is a likelihood ratio test for haplotype lengths.  The lengths are modeled with an exponential distribution.'
    SEARCH_ALIASES = ['hapLrt']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_haplrt.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['hapLrt']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),
                "target": ('STRING', {'description': 'argument: a zero base comma separated list of target individuals corresponding to VCF columns', 'default': ''}),
                "background": ('STRING', {'description': 'argument: a zero base comma separated list of background individuals corresponding to VCF columns', 'default': ''}),
                "type": ('STRING', {'description': 'argument: type of genotype likelihood: PL, GL, GT or GP', 'default': ''}),
            },
            "optional": {
                "region": ('STRING', {'description': 'argument: a genomic range to calculate hapLrt on in the format : "seqid:start-end" or "seqid"', 'default': ''}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['hapLrt']
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
