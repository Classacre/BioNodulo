"""``vcfannotategenotypes ``: Examine genotype correspondence. Annotate genotypes in the first file with genot.

Generated from the tool's own --help output in the pinned vcfannotategenotypes 1.0.15 image.
Help page SHA-256: 15b95f91d431bdfc02ee88cfa1f9c6f0c602e7641d0ab222d7eebfa1f7646ce5

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibVcfannotategenotypesNode(VcflibBase):
    """Examine genotype correspondence. Annotate genotypes in the first file with genotypes in the second"""

    NODE_ID = 'vcflib_vcfannotategenotypes'
    DISPLAY_NAME = 'vcfannotategenotypes'
    DESCRIPTION = 'Examine genotype correspondence. Annotate genotypes in the first file with genotypes in the second'
    SEARCH_ALIASES = ['vcfannotategenotypes']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_vcfannotategenotypes.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['vcfannotategenotypes']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),

            },
            "optional": {

            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['vcfannotategenotypes']
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
