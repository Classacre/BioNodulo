"""``popStats ``: General population genetic statistics for each SNP.

Generated from the tool's own --help output in the pinned popStats 1.0.15 image.
Help page SHA-256: 16c04112415c6420bc1de50e53b11028c837f972c7de7e42c29cdb38e61cb0a9

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibPopstatsNode(VcflibBase):
    """General population genetic statistics for each SNP"""

    NODE_ID = 'vcflib_popstats'
    DISPLAY_NAME = 'popStats'
    DESCRIPTION = 'General population genetic statistics for each SNP'
    SEARCH_ALIASES = ['popStats']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_popstats.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['popStats']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),
                "target": ('STRING', {'description': 'a zero based comma separated list of target individuals corresponding to VCF columns', 'default': ''}),
                "type": ('STRING', {'description': 'genotype likelihood format; genotype : GL,PL,GP', 'default': ''}),
            },
            "optional": {
                "region": ('STRING', {'description': 'a tabix compliant region : chr1:1-1000 or chr1', 'default': ''}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['popStats']
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
