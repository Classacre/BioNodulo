"""``unikmer merge``: Merge k-mers from sorted chunk files.

Generated from the tool's own --help output in the pinned unikmer 0.20.0 image.
Help page SHA-256: 114d9a5f3600ac941adb40f4c833c9b27fe0871bf50a88f159d62b59b2993fea

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import UnikmerBase


class UnikmerMergeNode(UnikmerBase):
    """Merge k-mers from sorted chunk files"""

    NODE_ID = 'unikmer_merge'
    DISPLAY_NAME = 'unikmer merge'
    SUBCOMMAND = 'merge'
    DESCRIPTION = 'Merge k-mers from sorted chunk files'
    SEARCH_ALIASES = ['unikmer', 'merge']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('unikmer_merge.out',)
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
                "force": ('BOOLEAN', {'description': 'overwrite tmp dir', 'default': False}),
                "is_dir": ('BOOLEAN', {'description': 'intput files are directory containing chunk files', 'default': False}),
                "keep_tmp_dir": ('BOOLEAN', {'description': 'keep tmp dir', 'default': False}),
                "max_open_files": ('INT', {'description': 'max number of open files', 'default': 400}),
                "pattern": ('STRING', {'description': 'chunk file pattern (regular expression)', 'default': '^chunk_\\\\d+\\\\.unik$'}),
                "repeated": ('BOOLEAN', {'description': 'only print duplicate k-mers', 'default': False}),
                "tmp_dir": ('STRING', {'description': 'directory for intermediate files', 'default': './'}),
                "unique": ('BOOLEAN', {'description': 'remove duplicate k-mers', 'default': False}),
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
