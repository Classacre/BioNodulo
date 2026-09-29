"""``seqfu rotate``: fu-rotate [options] -i POS [<fastq-file>...].

Generated from the tool's own --help output in the pinned seqfu seqfu 1.28.0 image.
Help page SHA-256: c745603ca3f1ad56fb3db7d2e859c8488be1e415df4b61c574800b09c5f22e2f

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import SeqfuBase


class SeqfuRotateNode(SeqfuBase):
    """fu-rotate [options] -i POS [<fastq-file>...]"""

    NODE_ID = 'seqfu_rotate'
    DISPLAY_NAME = 'seqfu rotate'
    SUBCOMMAND = 'rotate'
    DESCRIPTION = 'fu-rotate [options] -i POS [<fastq-file>...]'
    SEARCH_ALIASES = ['seqfu', 'rotate']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqfu_rotate.out',)
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
                "start_pos": ('STRING', {'description': 'Restart from base POS, where 1 is the first base', 'default': '1'}),
                "motif": ('STRING', {'description': 'Rotate sequences using motif STR as the new start, where STR is a string of bases', 'default': ''}),
                "skip_unmached": ('BOOLEAN', {'description': 'If a motif is provided, skip sequences that do not match the motif', 'default': False}),
                "revcomp": ('BOOLEAN', {'description': 'Also scan for reverse complemented motif', 'default': False}),
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
