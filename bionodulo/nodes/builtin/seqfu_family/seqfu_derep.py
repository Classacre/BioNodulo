"""``seqfu derep``: Dereplicate identical sequences and report cluster sizes.

Generated from the tool's own --help output in the pinned seqfu seqfu 1.28.0 image.
Help page SHA-256: 1d88f12d93ad918f5de97e2bd3746220cce0d2d4b21842af86f33341e1b17baf

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import SeqfuBase


class SeqfuDerepNode(SeqfuBase):
    """Dereplicate identical sequences and report cluster sizes"""

    NODE_ID = 'seqfu_derep'
    DISPLAY_NAME = 'seqfu derep'
    SUBCOMMAND = 'derep'
    DESCRIPTION = 'Dereplicate identical sequences and report cluster sizes'
    SEARCH_ALIASES = ['seqfu', 'derep']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqfu_derep.out',)
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
                "keep_name": ('BOOLEAN', {'description': 'Do not rename sequence (see -p), but use the first sequence name', 'default': False}),
                "ignore_size": ('BOOLEAN', {'description': "Do not count 'size=INT;' annotations (they will be stripped in any case)", 'default': False}),
                "min_size": ('INT', {'description': 'Print clusters with size equal or bigger than INT sequences', 'default': 0}),
                "prefix": ('STRING', {'description': 'Sequence name prefix', 'default': 'seq'}),
                "md5": ('BOOLEAN', {'description': 'Use MD5 as sequence name (overrides other parameters)', 'default': False}),
                "json": ('STRING', {'description': 'Save dereplication metadata to JSON file', 'default': ''}),
                "separator": ('STRING', {'description': 'Sequence name separator', 'default': '.'}),
                "line_width": ('INT', {'description': 'FASTA line width (0: unlimited)', 'default': 0}),
                "min_length": ('INT', {'description': 'Discard sequences shorter than MIN_LEN', 'default': 0}),
                "max_length": ('INT', {'description': 'Discard sequences longer than MAX_LEN', 'default': 0}),
                "size_as_comment": ('BOOLEAN', {'description': 'Print cluster size as comment, not in sequence name', 'default': False}),
                "add_len": ('BOOLEAN', {'description': 'Add length to sequence', 'default': False}),
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
