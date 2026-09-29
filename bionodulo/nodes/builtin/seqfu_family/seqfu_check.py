"""``seqfu check``: seqfu check [options] --dir <FQDIR>.

Generated from the tool's own --help output in the pinned seqfu seqfu 1.28.0 image.
Help page SHA-256: d8d55c079f1c3c24e4f1b71dfbbefcb27100e1837fc69ea83414a9d214855bcb

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import SeqfuBase


class SeqfuCheckNode(SeqfuBase):
    """seqfu check [options] --dir <FQDIR>"""

    NODE_ID = 'seqfu_check'
    DISPLAY_NAME = 'seqfu check'
    SUBCOMMAND = 'check'
    DESCRIPTION = 'seqfu check [options] --dir <FQDIR>'
    SEARCH_ALIASES = ['seqfu', 'check']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqfu_check.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://telatin.github.io/seqfu2/'
    REQUIRED_EXECUTABLES = ['seqfu']
    REQUIRED_CONDA_PACKAGES = ['seqfu']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input sequence file'}),

            },
            "optional": {
                "deep": ('BOOLEAN', {'description': 'Perform a deep check of the file and will not lsupport multiline Sanger FASTQ [default: false]', 'default': False}),
                "no_paired": ('BOOLEAN', {'description': 'Disable autodetection of second pair', 'default': False}),
                "safe_exit": ('BOOLEAN', {'description': 'Exit with 0 even if errors are found', 'default': False}),
                "thousands": ('BOOLEAN', {'description': 'Print numbers with thousands separator', 'default': False}),
                "debug": ('BOOLEAN', {'description': 'Debug output', 'default': False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['seqfu', cls.SUBCOMMAND]
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
