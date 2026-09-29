"""``unikmer dump``: Convert plain k-mer text to binary format.

Generated from the tool's own --help output in the pinned unikmer 0.20.0 image.
Help page SHA-256: 1b7f6d07e868bd167701d8ecc4154fddc2ee2f230f1339c4ef87df3c88be5326

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import UnikmerBase


class UnikmerDumpNode(UnikmerBase):
    """Convert plain k-mer text to binary format"""

    NODE_ID = 'unikmer_dump'
    DISPLAY_NAME = 'unikmer dump'
    SUBCOMMAND = 'dump'
    DESCRIPTION = 'Convert plain k-mer text to binary format'
    SEARCH_ALIASES = ['unikmer', 'dump']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('unikmer_dump.out',)
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
                "canonical": ('BOOLEAN', {'description': 'save the canonical k-mers', 'default': False}),
                "canonical_only": ('BOOLEAN', {'description': 'only save the canonical k-mers. This flag overides -K/--canonical', 'default': False}),
                "hash": ('BOOLEAN', {'description': 'save hash of k-mer, automatically on for k>32. This flag overides global flag -c/--compact', 'default': False}),
                "hashed": ('BOOLEAN', {'description': 'giving hash values of k-mers, This flag overides global flag -c/--compact', 'default': False}),
                "kmer_len": ('INT', {'description': 'k-mer length', 'default': ''}),
                "sorted": ('BOOLEAN', {'description': 'input k-mers are sorted', 'default': False}),
                "taxid": ('STRING', {'description': 'global taxid', 'default': ''}),
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
