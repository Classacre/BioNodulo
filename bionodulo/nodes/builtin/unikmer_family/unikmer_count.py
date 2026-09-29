"""``unikmer count``: Generate k-mers (sketch) from FASTA/Q sequences.

Generated from the tool's own --help output in the pinned unikmer 0.20.0 image.
Help page SHA-256: cdd6ec75fd64b367c61e9182e9f1ff1b82cd6c97a13aa37cb724222c664a6b3c

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import UnikmerBase


class UnikmerCountNode(UnikmerBase):
    """Generate k-mers (sketch) from FASTA/Q sequences"""

    NODE_ID = 'unikmer_count'
    DISPLAY_NAME = 'unikmer count'
    SUBCOMMAND = 'count'
    DESCRIPTION = 'Generate k-mers (sketch) from FASTA/Q sequences'
    SEARCH_ALIASES = ['unikmer', 'count']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('unikmer_count.out',)
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
                "canonical": ('BOOLEAN', {'description': 'only keep the canonical k-mers', 'default': False}),
                "circular": ('BOOLEAN', {'description': 'circular genome', 'default': False}),
                "hash": ('BOOLEAN', {'description': 'save hash of k-mer, automatically on for k>32. This flag overides global flag -c/--compact', 'default': False}),
                "kmer_len": ('INT', {'description': 'k-mer length', 'default': ''}),
                "linear": ('BOOLEAN', {'description': 'output k-mers in linear order, duplicate k-mers are not removed', 'default': False}),
                "minimizer_w": ('INT', {'description': 'minimizer window size', 'default': ''}),
                "more_verbose": ('BOOLEAN', {'description': 'print extra verbose information', 'default': False}),
                "parse_taxid": ('BOOLEAN', {'description': 'parse taxid from FASTA/Q header', 'default': False}),
                "parse_taxid_regexp": ('STRING', {'description': 'regular expression for passing taxid', 'default': ''}),
                "repeated": ('BOOLEAN', {'description': 'only count duplicate k-mers, for removing singleton in FASTQ', 'default': False}),
                "scale": ('INT', {'description': 'scale/down-sample factor', 'default': 1}),
                "seq_name_filter": ('STRING', {'description': 'list of regular expressions for filtering out sequences by header/name, case ignored.', 'default': ''}),
                "sort": ('BOOLEAN', {'description': 'sort k-mers, this significantly reduce file size for k<=25. This flag overides global flag -c/--compact', 'default': False}),
                "syncmer_s": ('INT', {'description': 'closed syncmer length', 'default': ''}),
                "taxid": ('STRING', {'description': 'global taxid', 'default': ''}),
                "unique": ('BOOLEAN', {'description': 'only count unique k-mers, which are not duplicate', 'default': False}),
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
