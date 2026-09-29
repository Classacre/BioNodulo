"""``vcfcheck ``: Validate integrity and identity of the VCF by verifying that the VCF.

Generated from the tool's own --help output in the pinned vcfcheck 1.0.15 image.
Help page SHA-256: ada16763fd24b829d9afd2686e6f0c30faff3987b848a41bb6441406f578f48d

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibVcfcheckNode(VcflibBase):
    """Validate integrity and identity of the VCF by verifying that the VCF"""

    NODE_ID = 'vcflib_vcfcheck'
    DISPLAY_NAME = 'vcfcheck'
    DESCRIPTION = 'Validate integrity and identity of the VCF by verifying that the VCF'
    SEARCH_ALIASES = ['vcfcheck']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_vcfcheck.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['vcfcheck']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),

            },
            "optional": {
                "fasta_reference": ('STRING', {'description': 'reference file to use to obtain primer sequences.', 'default': ''}),
                "exclude_failures": ('BOOLEAN', {'description': "If a record fails, don't print it.  Otherwise do.", 'default': False}),
                "keep_failures": ('BOOLEAN', {'description': 'Print if the record fails, otherwise not.', 'default': False}),
                "ignore_case": ('BOOLEAN', {'description': 'Ignore case differences between FASTA reference and vcf.', 'default': False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['vcfcheck']
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
