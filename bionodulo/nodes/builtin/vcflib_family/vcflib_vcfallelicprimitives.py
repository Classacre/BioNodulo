"""``vcfallelicprimitives ``: Realign reference and alternate alleles with SW or WF, parsing out.

Generated from the tool's own --help output in the pinned vcfallelicprimitives 1.0.15 image.
Help page SHA-256: daffbb6bf0d95c49a8f41dc78da93e344ff691dc03176d9c320aad3ac6fc8493

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibVcfallelicprimitivesNode(VcflibBase):
    """Realign reference and alternate alleles with SW or WF, parsing out"""

    NODE_ID = 'vcflib_vcfallelicprimitives'
    DISPLAY_NAME = 'vcfallelicprimitives'
    DESCRIPTION = 'Realign reference and alternate alleles with SW or WF, parsing out'
    SEARCH_ALIASES = ['vcfallelicprimitives']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_vcfallelicprimitives.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['vcfallelicprimitives']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),

            },
            "optional": {
                "algorithm": ('STRING', {'description': 'Choose algorithm SW (Smith-Waterman) or WF wavefront (default: WF)', 'default': ''}),
                "use_mnps": ('BOOLEAN', {'description': 'Retain MNPs as separate events (default: false).', 'default': False}),
                "tag_parsed": ('STRING', {'description': 'Annotate decomposed records with the source record position (default: ORIGIN).', 'default': ''}),
                "max_length": ('STRING', {'description': 'Do not manipulate records in which either the ALT or REF is longer than LEN (default: unlimited).', 'default': ''}),
                "keep_info": ('BOOLEAN', {'description': "Maintain site and allele-level annotations when decomposing.  Note that in many cases, such as multisample VCFs, these won't be valid post decomposition.  For biallelic loci in single-sample VCFs, they should be used with caution.", 'default': False}),
                "debug": ('BOOLEAN', {'description': 'debug mode.', 'default': False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['vcfallelicprimitives']
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
