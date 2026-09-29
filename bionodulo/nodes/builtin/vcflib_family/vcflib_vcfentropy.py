"""``vcfentropy ``: Annotate VCF records with the Shannon entropy of flanking sequence..

Generated from the tool's own --help output in the pinned vcfentropy 1.0.15 image.
Help page SHA-256: 37485f36f7215ee1d06c4660e50ac82c08c7bbc92c44cf75d6c5107b9dcac7d2

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibVcfentropyNode(VcflibBase):
    """Annotate VCF records with the Shannon entropy of flanking sequence."""

    NODE_ID = 'vcflib_vcfentropy'
    DISPLAY_NAME = 'vcfentropy'
    DESCRIPTION = 'Annotate VCF records with the Shannon entropy of flanking sequence.'
    SEARCH_ALIASES = ['vcfentropy']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_vcfentropy.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['vcfentropy']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),

            },
            "optional": {
                "fasta_reference": ('STRING', {'description': 'reference file to use to obtain flanking sequences', 'default': ''}),
                "window_size": ('STRING', {'description': 'Size of the window over which to calculate entropy', 'default': ''}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['vcfentropy']
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
