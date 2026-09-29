"""``seqfu orf``: orf - extract ORF from nucleotide sequences.

Generated from the tool's own --help output in the pinned seqfu seqfu 1.28.0 image.
Help page SHA-256: ec4ddfed10efd698e6f87c782cc2582fed4b574f9b787c300a8ed7acfb47a1f0

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import SeqfuBase


class SeqfuOrfNode(SeqfuBase):
    """orf - extract ORF from nucleotide sequences"""

    NODE_ID = 'seqfu_orf'
    DISPLAY_NAME = 'seqfu orf'
    SUBCOMMAND = 'orf'
    DESCRIPTION = 'orf - extract ORF from nucleotide sequences'
    SEARCH_ALIASES = ['seqfu', 'orf']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqfu_orf.out',)
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
                "R1": ('STRING', {'description': 'First paired end file', 'default': ''}),
                "R2": ('STRING', {'description': 'Second paired end file', 'default': ''}),
                "min_size": ('INT', {'description': 'Minimum ORF size (aa)', 'default': 25}),
                "prefix": ('STRING', {'description': 'Rename reads using this prefix', 'default': ''}),
                "scan_reverse": ('BOOLEAN', {'description': 'Also scan reverse complemented sequences', 'default': False}),
                "code": ('INT', {'description': 'NCBI Genetic code to use', 'default': 1}),
                "min_read_len": ('INT', {'description': 'Minimum read length to process', 'default': 25}),
                "translate": ('BOOLEAN', {'description': 'Consider input CDS', 'default': False}),
                "join": ('BOOLEAN', {'description': 'Attempt Paired-End joining', 'default': False}),
                "min_overlap": ('INT', {'description': 'Minimum PE overlap', 'default': 12}),
                "max_overlap": ('INT', {'description': 'Maximum PE overlap', 'default': 200}),
                "min_identity": ('FLOAT', {'description': 'Minimum sequence identity in overlap', 'default': 0.8}),
                "codes": ('BOOLEAN', {'description': 'Print NCBI genetic codes and exit', 'default': False}),
                "pool_size": ('INT', {'description': 'Size of the sequences array to be processed by each working thread [default: 250] forced processing/flush; 0 = auto [default: 0]', 'default': ''}),
                "debug": ('BOOLEAN', {'description': 'Print debug log', 'default': False}),
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
