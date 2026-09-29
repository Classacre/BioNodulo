"""``vcfsample2info ``: Take annotations given in the per-sample fields and add the mean, median, min, o.

Generated from the tool's own --help output in the pinned vcfsample2info 1.0.15 image.
Help page SHA-256: 401453e7ac3e37a85ac18286324e69ed4147c03ec79938ea3e9bb9a98b5e3587

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibVcfsample2infoNode(VcflibBase):
    """Take annotations given in the per-sample fields and add the mean, median, min, or max"""

    NODE_ID = 'vcflib_vcfsample2info'
    DISPLAY_NAME = 'vcfsample2info'
    DESCRIPTION = 'Take annotations given in the per-sample fields and add the mean, median, min, or max'
    SEARCH_ALIASES = ['vcfsample2info']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_vcfsample2info.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['vcfsample2info']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),

            },
            "optional": {
                "field": ('STRING', {'description': 'Add information about this field in samples to INFO column', 'default': ''}),
                "info": ('STRING', {'description': 'Store the computed statistic in this info field', 'default': ''}),
                "average": ('BOOLEAN', {'description': 'Take the mean of samples for field', 'default': False}),
                "median": ('BOOLEAN', {'description': 'Use the median', 'default': False}),
                "min": ('BOOLEAN', {'description': 'Use the min', 'default': False}),
                "max": ('BOOLEAN', {'description': 'Use the max', 'default': False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['vcfsample2info']
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
