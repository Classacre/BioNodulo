"""``sequenceDiversity ``: The sequenceDiversity program calculates two popular metrics of  haplotype diver.

Generated from the tool's own --help output in the pinned sequenceDiversity 1.0.15 image.
Help page SHA-256: 6b2b9a065448bbe4a2acf40f3b790bebae0eeaef061b3b063087c7774851871b

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibSequencediversityNode(VcflibBase):
    """The sequenceDiversity program calculates two popular metrics of  haplotype diversity: pi and"""

    NODE_ID = 'vcflib_sequencediversity'
    DISPLAY_NAME = 'sequenceDiversity'
    DESCRIPTION = 'The sequenceDiversity program calculates two popular metrics of  haplotype diversity: pi and'
    SEARCH_ALIASES = ['sequenceDiversity']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_sequencediversity.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['sequenceDiversity']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),
                "target": ('STRING', {'description': 'argument: a zero base comma separated list of target individuals corresponding to VCF columns', 'default': ''}),
                "type": ('STRING', {'description': 'argument: type of genotype likelihood: PL, GL or GP', 'default': ''}),
            },
            "optional": {
                "af": ('STRING', {'description': 'sites less than af  are filtered out; default is 0', 'default': ''}),
                "region": ('STRING', {'description': 'argument: a tabix compliant region : "seqid:0-100" or "seqid"', 'default': ''}),
                "window": ('STRING', {'description': 'argument: the number of SNPs per window; default is 20', 'default': ''}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['sequenceDiversity']
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
