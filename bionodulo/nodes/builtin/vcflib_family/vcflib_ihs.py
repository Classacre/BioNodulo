"""``iHS ``: iHS calculates the integrated ratio of haplotype decay between the reference and.

Generated from the tool's own --help output in the pinned iHS 1.0.15 image.
Help page SHA-256: 77d4b668861bd4d7c62256db1c3eec2036ba553ba8603d58e559c520174bfc2e

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibIhsNode(VcflibBase):
    """iHS calculates the integrated ratio of haplotype decay between the reference and non-reference allele."""

    NODE_ID = 'vcflib_ihs'
    DISPLAY_NAME = 'iHS'
    DESCRIPTION = 'iHS calculates the integrated ratio of haplotype decay between the reference and non-reference allele.'
    SEARCH_ALIASES = ['iHS']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_ihs.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['iHS']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),
                "target": ('STRING', {'description': 'A zero base comma separated list of target individuals corresponding to VCF columns', 'default': ''}),
                "region": ('STRING', {'description': 'A tabix compliant genomic range format: "seqid:start-end" or "seqid"', 'default': ''}),
                "type": ('STRING', {'description': 'Genotype likelihood format: GT,PL,GL,GP', 'default': ''}),
            },
            "optional": {
                "af": ('FLOAT', {'description': 'Alternative alleles with frquences less than [0.05] are skipped.', 'default': ''}),
                "threads": ('INT', {'description': 'Number of CPUS', 'default': 1}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['iHS']
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
