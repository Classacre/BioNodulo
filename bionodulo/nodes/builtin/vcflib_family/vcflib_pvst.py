"""``pVst ``: pVst calculates vst, a measure of CNV stratification..

Generated from the tool's own --help output in the pinned pVst 1.0.15 image.
Help page SHA-256: d2a5075ebf6ad9a61afa643ca6ecbecaed511762494e3c5469c02223d667267c

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibPvstNode(VcflibBase):
    """pVst calculates vst, a measure of CNV stratification."""

    NODE_ID = 'vcflib_pvst'
    DISPLAY_NAME = 'pVst'
    DESCRIPTION = 'pVst calculates vst, a measure of CNV stratification.'
    SEARCH_ALIASES = ['pVst']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_pvst.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['pVst']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),
                "target": ('STRING', {'description': 'argument: a zero based comma separated list of target individuals corresponding to VCF columns', 'default': ''}),
                "background": ('STRING', {'description': 'argument: a zero based comma separated list of background individuals corresponding to VCF columns', 'default': ''}),
                "type": ('STRING', {'description': 'argument: the genotype field with the copy number: e.g. CN|CNF', 'default': ''}),
            },
            "optional": {
                "region": ('STRING', {'description': 'argument: a tabix compliant genomic range : seqid or seqid:start-end', 'default': ''}),
                "cpu": ('STRING', {'description': 'argument: number of CPUs', 'default': '1'}),
                "per": ('STRING', {'description': 'argument: number of permutations', 'default': '1000'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['pVst']
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
