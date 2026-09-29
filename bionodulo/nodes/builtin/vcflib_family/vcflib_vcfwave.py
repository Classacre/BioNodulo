"""``vcfwave ``: Realign reference and alternate alleles with WFA, parsing out the.

Generated from the tool's own --help output in the pinned vcfwave 1.0.15 image.
Help page SHA-256: b2744125dd9a67cc625bf87ff30a30d1e25fa3ecb45e2cd36bc6f424433d09fb

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibVcfwaveNode(VcflibBase):
    """Realign reference and alternate alleles with WFA, parsing out the"""

    NODE_ID = 'vcflib_vcfwave'
    DISPLAY_NAME = 'vcfwave'
    DESCRIPTION = 'Realign reference and alternate alleles with WFA, parsing out the'
    SEARCH_ALIASES = ['vcfwave']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_vcfwave.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['vcfwave']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),

            },
            "optional": {
                "wf_params": ('STRING', {'description': 'use the given BiWFA params (default: 0,19,39,3,81,1) format=match,mismatch,gap1-open,gap1-ext,gap2-open,gap2-ext', 'default': ''}),
                "tag_parsed": ('STRING', {'description': 'Annotate decomposed records with the source record position (default: ORIGIN).', 'default': ''}),
                "max_length": ('STRING', {'description': 'Do not manipulate records in which either the ALT or REF is longer than LEN (default: unlimited).', 'default': ''}),
                "inv_kmer": ('STRING', {'description': 'Length of k-mer to use for inversion detection sketching (default: 17).', 'default': ''}),
                "inv_min": ('STRING', {'description': 'Minimum allele length to consider for inverted alignment (default: 64).', 'default': ''}),
                "threads": ('STRING', {'description': 'Use this many threads for variant decomposition For most datasets threading may actually slow vcfwave down.', 'default': 'default is 1'}),
                "debug": ('BOOLEAN', {'description': 'Debug mode.', 'default': False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['vcfwave']
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
