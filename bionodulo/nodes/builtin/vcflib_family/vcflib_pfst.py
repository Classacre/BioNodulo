"""``pFst ``: pFst is a probabilistic approach for detecting differences in allele frequencies.

Generated from the tool's own --help output in the pinned pFst 1.0.15 image.
Help page SHA-256: 45caf28ef88a49729c373047f2ce1d6f0038f9763ded937a2ea5ead5b86c8728

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibPfstNode(VcflibBase):
    """pFst is a probabilistic approach for detecting differences in allele frequencies between two populations."""

    NODE_ID = 'vcflib_pfst'
    DISPLAY_NAME = 'pFst'
    DESCRIPTION = 'pFst is a probabilistic approach for detecting differences in allele frequencies between two populations.'
    SEARCH_ALIASES = ['pFst']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_pfst.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['pFst']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),
                "target": ('STRING', {'description': 'argument: a zero based comma separated list of target individuals corresponding to VCF columns', 'default': ''}),
                "background": ('STRING', {'description': 'argument: a zero based comma separated list of background individuals corresponding to VCF columns', 'default': ''}),
                "type": ('STRING', {'description': 'argument: genotype likelihood format ; genotypes: GP, GL or PL; pooled: PO', 'default': ''}),
            },
            "optional": {
                "deltaaf": ('STRING', {'description': 'argument: skip sites where the difference in allele frequencies is less than deltaaf, default is zero', 'default': ''}),
                "region": ('STRING', {'description': 'argument: a tabix compliant genomic range : seqid or seqid:start-end', 'default': ''}),
                "counts": ('STRING', {'description': 'switch  : use genotype counts rather than genotype likelihoods to estimate parameters, default false', 'default': ''}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['pFst']
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
