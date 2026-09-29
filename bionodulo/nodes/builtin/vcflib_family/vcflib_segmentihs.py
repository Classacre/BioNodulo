"""``segmentIhs ``: Creates genomic segments (bed file) for regions with high wcFst.

Generated from the tool's own --help output in the pinned segmentIhs 1.0.15 image.
Help page SHA-256: 000ce9c575bfbd3bf6540794419ccf8ba67ac500b99e50ebbd2aa560d0044a91

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibSegmentihsNode(VcflibBase):
    """Creates genomic segments (bed file) for regions with high wcFst"""

    NODE_ID = 'vcflib_segmentihs'
    DISPLAY_NAME = 'segmentIhs'
    DESCRIPTION = 'Creates genomic segments (bed file) for regions with high wcFst'
    SEARCH_ALIASES = ['segmentIhs']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_segmentihs.out',)
    STDOUT_OUTPUT_INDEX = 0
    FLAG_TOKENS = {'f': '-f', 's': '-s'}
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['segmentIhs']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),
                "f": ('STRING', {'description': 'Output from normalizeIHS', 'default': ''}),
            },
            "optional": {
                "s": ('STRING', {'description': 'High absolute iHS cutoff', 'default': '2'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['segmentIhs']
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
