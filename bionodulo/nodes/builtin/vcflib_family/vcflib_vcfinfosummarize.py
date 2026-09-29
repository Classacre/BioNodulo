"""``vcfinfosummarize ``: Take annotations given in the per-sample fields and add the mean, median, min, o.

Generated from the tool's own --help output in the pinned vcfinfosummarize 1.0.15 image.
Help page SHA-256: eba6ecbad8405682eecbd8cfc00ddf8950ca728df41bd89f082187e161dab693

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import VcflibBase


class VcflibVcfinfosummarizeNode(VcflibBase):
    """Take annotations given in the per-sample fields and add the mean, median, min, or max"""

    NODE_ID = 'vcflib_vcfinfosummarize'
    DISPLAY_NAME = 'vcfinfosummarize'
    DESCRIPTION = 'Take annotations given in the per-sample fields and add the mean, median, min, or max'
    SEARCH_ALIASES = ['vcfinfosummarize']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('vcflib_vcfinfosummarize.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    REQUIRED_EXECUTABLES = ['vcfinfosummarize']
    REQUIRED_CONDA_PACKAGES = ['vcflib']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input VCF file (or the positional file the tool expects)'}),

            },
            "optional": {
                "field": ('STRING', {'description': 'Summarize this field in the INFO column', 'default': ''}),
                "info": ('STRING', {'description': 'Store the computed statistic in this info field', 'default': ''}),
                "average": ('BOOLEAN', {'description': 'Take the mean for field', 'default': False}),
                "median": ('BOOLEAN', {'description': 'Use the median', 'default': False}),
                "min": ('BOOLEAN', {'description': 'Use the min', 'default': False}),
                "max": ('BOOLEAN', {'description': 'Use the max', 'default': False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['vcfinfosummarize']
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
