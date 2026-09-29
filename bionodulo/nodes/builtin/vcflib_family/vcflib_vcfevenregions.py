"""``vcfevenregions ``: Generates a list of regions, e.g. chr20:10..30 using the variant.

Generated from the tool's own --help output in the pinned vcfevenregions 1.0.15 image.
Help page SHA-256: a83778630085e9c8efa73821b8da766e7870bbbf7c57868953d82e42b245c084

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibVcfevenregionsNode(VcflibBase):
    """Generates a list of regions, e.g. chr20:10..30 using the variant"""

    NODE_ID = 'vcflib_vcfevenregions'
    DISPLAY_NAME = 'vcfevenregions'
    DESCRIPTION = 'Generates a list of regions, e.g. chr20:10..30 using the variant'
    SEARCH_ALIASES = ['vcfevenregions']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_vcfevenregions.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['vcfevenregions']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),

            },
            "optional": {
                "fasta_reference": ('STRING', {'description': 'FASTA reference file to use to obtain primer sequences.', 'default': ''}),
                "number_of_regions": ('STRING', {'description': 'The number of desired regions.', 'default': ''}),
                "number_of_positions": ('STRING', {'description': 'The number of positions per region.', 'default': ''}),
                "offset": ('STRING', {'description': 'Add an offset to region positioning, to avoid boundary related artifacts in downstream processing.', 'default': ''}),
                "overlap": ('STRING', {'description': 'The number of sites to overlap between regions.  Default 0.', 'default': ''}),
                "separator": ('STRING', {'description': "Specify string to use to separate region output.  Default '-'", 'default': ''}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['vcfevenregions']
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
