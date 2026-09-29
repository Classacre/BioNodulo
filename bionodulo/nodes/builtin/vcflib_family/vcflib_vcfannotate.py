"""``vcfannotate ``: Intersect the records in the VCF file with targets provided in a BED file..

Generated from the tool's own --help output in the pinned vcfannotate 1.0.15 image.
Help page SHA-256: 5039ee7c4ed2599cbf4be4de10341c3d88c1bd497ff22c0a3657ee09b1470df3

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibVcfannotateNode(VcflibBase):
    """Intersect the records in the VCF file with targets provided in a BED file."""

    NODE_ID = 'vcflib_vcfannotate'
    DISPLAY_NAME = 'vcfannotate'
    DESCRIPTION = 'Intersect the records in the VCF file with targets provided in a BED file.'
    SEARCH_ALIASES = ['vcfannotate']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_vcfannotate.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['vcfannotate']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),

            },
            "optional": {
                "bed": ('STRING', {'description': 'use annotations provided by this BED file', 'default': ''}),
                "key": ('STRING', {'description': 'use this INFO field key for the annotations', 'default': ''}),
                "default": ('STRING', {'description': 'use this INFO field key for records without annotations', 'default': ''}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['vcfannotate']
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
