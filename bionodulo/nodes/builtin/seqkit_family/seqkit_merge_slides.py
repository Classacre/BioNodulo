"""``seqkit merge-slides``: merge sliding windows generated from seqkit sliding.

Generated from the tool's own --help output in the pinned seqkit v2.13.0 image.
Help page SHA-256: dab0c720459f992bbb2b16b6996a4101e2214a1dd1e169865137926e0db23ff3

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqkitBase


class SeqkitMergeSlidesNode(SeqkitBase):
    """merge sliding windows generated from seqkit sliding"""

    NODE_ID = 'seqkit_merge_slides'
    DISPLAY_NAME = 'seqkit merge-slides'
    SUBCOMMAND = 'merge-slides'
    DESCRIPTION = 'merge sliding windows generated from seqkit sliding'
    SEARCH_ALIASES = ['seqkit', 'merge-slides']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqkit_merge_slides.out',)
    DOCUMENTATION_URL = 'https://bioinf.shenwei.me/seqkit/'
    REQUIRED_EXECUTABLES = ['seqkit']
    REQUIRED_CONDA_PACKAGES = ['seqkit']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ("FILE", {"description": 'Input FASTA/FASTQ file'}),

            },
            "optional": {
                "buffer_size": ('STRING', {'description': 'size of buffer, supported unit: K, M, G. You need increase the value when "bufio.Scanner: token too long" error reported (default "1G")', 'default': ''}),
                "comment_line_prefix": ('STRING', {'description': 'comment line prefix', 'default': '[#,//]'}),
                "max_gap": ('INT', {'description': 'maximum distance of starting positions of two adjacent regions, 0 for no limitation, 1 for no merging.', 'default': ''}),
                "min_overlap": ('INT', {'description': 'minimum overlap of two adjacent regions, recommend $sliding_step_size - 1. (default 1)', 'default': ''}),
                "regexp": ('STRING', {'description': 'regular expression for extract the reference name and window position. (default "^(.+)_sliding:(\\\\d+)\\\\-(\\\\d+)")', 'default': ''}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = ['seqkit', cls.SUBCOMMAND]
        # Required flags must be rendered too. Iterating only "optional" silently
        # dropped every empirically-required flag (csvtk mutate --name and friends).
        declared_types = cls.INPUT_TYPES()
        for category in ("required", "optional"):
            for name, spec in declared_types.get(category, {}).items():
                if name in ('sequence',):
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
        command.extend(['-o', str(output_dir / cls.OUTPUT_FILENAMES[0])])
        command.append(str(inputs.get('sequence', "")))
        return command
