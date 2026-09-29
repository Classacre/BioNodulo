"""``vcfremap ``: For each alternate allele, attempt to realign against the reference with lowered.

Generated from the tool's own --help output in the pinned vcfremap 1.0.15 image.
Help page SHA-256: 93d8c261cd38e6ce4a13a61bbe50004c132d1daf4dc282ba1428bee9164949c2

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibVcfremapNode(VcflibBase):
    """For each alternate allele, attempt to realign against the reference with lowered gap open penalty."""

    NODE_ID = 'vcflib_vcfremap'
    DISPLAY_NAME = 'vcfremap'
    DESCRIPTION = 'For each alternate allele, attempt to realign against the reference with lowered gap open penalty.'
    SEARCH_ALIASES = ['vcfremap']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_vcfremap.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['vcfremap']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),

            },
            "optional": {
                "ref_window_size": ('STRING', {'description': 'align using this many bases flanking each side of the reference allele', 'default': ''}),
                "alt_window_size": ('STRING', {'description': 'align using this many flanking bases from the reference around each alternate allele', 'default': ''}),
                "reference": ('STRING', {'description': 'FASTA reference file, required with -i and -u', 'default': ''}),
                "match_score": ('STRING', {'description': 'match score for SW algorithm', 'default': ''}),
                "mismatch_score": ('STRING', {'description': 'mismatch score for SW algorithm', 'default': ''}),
                "gap_open_penalty": ('STRING', {'description': 'gap open penalty for SW algorithm', 'default': ''}),
                "gap_extend_penalty": ('STRING', {'description': 'gap extension penalty for SW algorithm', 'default': ''}),
                "entropy_gap_open": ('BOOLEAN', {'description': 'use entropy scaling for the gap open penalty', 'default': False}),
                "repeat_gap_extend": ('STRING', {'description': 'penalize non-repeat-unit gaps in repeat sequence', 'default': ''}),
                "adjust_vcf": ('STRING', {'description': 'supply a new cigar as TAG in the output VCF', 'default': ''}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['vcfremap']
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
