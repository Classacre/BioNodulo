"""``vcfstreamsort ``: Sorts the input (either stdin or file) using a streaming sort algorithm. Guarant.

Generated from the tool's own --help output in the pinned vcfstreamsort 1.0.15 image.
Help page SHA-256: 51186264af41e07568c2bb8cae053847cc947cfcbb2052fbf271ddd199dd0059

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibVcfstreamsortNode(VcflibBase):
    """Sorts the input (either stdin or file) using a streaming sort algorithm. Guarantees that the positional order is correct provided out-of-order variant"""

    NODE_ID = 'vcflib_vcfstreamsort'
    DISPLAY_NAME = 'vcfstreamsort'
    DESCRIPTION = 'Sorts the input (either stdin or file) using a streaming sort algorithm. Guarantees that the positional order is correct provided out-of-order variants are no more than 100 positions in the VCF file a'
    SEARCH_ALIASES = ['vcfstreamsort']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_vcfstreamsort.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['vcfstreamsort']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),

            },
            "optional": {
                "window": ('STRING', {'description': 'number of sites to sort', 'default': 'default 10000'}),
                "all": ('STRING', {'description': 'load all sites and then sort in memory', 'default': ''}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['vcfstreamsort']
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
