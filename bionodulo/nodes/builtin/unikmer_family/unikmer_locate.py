"""``unikmer locate``: Locate k-mers in genome.

Generated from the tool's own --help output in the pinned unikmer 0.20.0 image.
Help page SHA-256: 8c9dbefde652a1b795539c283981200b608f83b909bbdc707879835008b84dce

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import UnikmerBase


class UnikmerLocateNode(UnikmerBase):
    """Locate k-mers in genome"""

    NODE_ID = 'unikmer_locate'
    DISPLAY_NAME = 'unikmer locate'
    SUBCOMMAND = 'locate'
    DESCRIPTION = 'Locate k-mers in genome'
    SEARCH_ALIASES = ['unikmer', 'locate']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('unikmer_locate.out',)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/unikmer/'
    REQUIRED_EXECUTABLES = ['unikmer']
    REQUIRED_CONDA_PACKAGES = ['unikmer']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'input': ("FILE", {"description": 'Input k-mer file (.unik) or FASTA/Q file'}),

            },
            "optional": {
                "circular": ('BOOLEAN', {'description': 'circular genome. type "unikmer locate -h" for details', 'default': False}),
                "genome": ('STRING', {'description': 'genomes in (gzipped) fasta file(s)', 'default': ''}),
                "seq_name_filter": ('STRING', {'description': 'list of regular expressions for filtering out sequences by header/name, case ignored', 'default': ''}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['unikmer', cls.SUBCOMMAND]
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
        command.extend(['--out-prefix', "-"])
        command.append(str(inputs.get('input', "")))
        return command
