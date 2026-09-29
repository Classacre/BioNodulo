"""``seqfu trim``: Trim and quality-filter FASTQ reads.

Generated from the tool's own --help output in the pinned seqfu seqfu 1.28.0 image.
Help page SHA-256: 907e6fdb49000b2da943d1386a87bcdce102866c89e484ccf0ba78cc18a54f97

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import SeqfuBase


class SeqfuTrimNode(SeqfuBase):
    """Trim and quality-filter FASTQ reads"""

    NODE_ID = 'seqfu_trim'
    DISPLAY_NAME = 'seqfu trim'
    SUBCOMMAND = 'trim'
    DESCRIPTION = 'Trim and quality-filter FASTQ reads'
    SEARCH_ALIASES = ['seqfu', 'trim']
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    OUTPUT_FILENAMES = ('seqfu_trim.out',)
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
                "r1": ('STRING', {'description': 'R1 file for paired-end', 'default': ''}),
                "r2": ('STRING', {'description': 'R2 file for paired-end (auto-detect if not specified)', 'default': ''}),
                "for_tag": ('STRING', {'description': 'Pattern for R1 files', 'default': 'auto'}),
                "rev_tag": ('STRING', {'description': 'Pattern for R2 files', 'default': 'auto'}),
                "r1_suffix": ('STRING', {'description': 'R1 output suffix', 'default': '_R1.fastq'}),
                "r2_suffix": ('STRING', {'description': 'R2 output suffix', 'default': '_R2.fastq'}),
                "compress": ('BOOLEAN', {'description': 'Compress output with gzip', 'default': False}),
                "trim_front": ('STRING', {'description': "Trim N bases from 5' end", 'default': '0'}),
                "trim_tail": ('STRING', {'description': "Trim N bases from 3' end", 'default': '0'}),
                "cut_front": ('BOOLEAN', {'description': "Enable 5' sliding window trimming", 'default': False}),
                "cut_front_window": ('STRING', {'description': 'Window size for cut-front', 'default': '4'}),
                "cut_front_qual": ('STRING', {'description': 'Quality threshold for cut-front', 'default': '20'}),
                "cut_tail": ('BOOLEAN', {'description': "Enable 3' sliding window trimming", 'default': False}),
                "cut_tail_window": ('STRING', {'description': 'Window size for cut-tail', 'default': '4'}),
                "cut_tail_qual": ('STRING', {'description': 'Quality threshold for cut-tail', 'default': '20'}),
                "cut_right": ('BOOLEAN', {'description': 'Enable right-side sliding window (precedence over cut-tail)', 'default': False}),
                "cut_right_window": ('STRING', {'description': 'Window size for cut-right', 'default': '4'}),
                "cut_right_qual": ('STRING', {'description': 'Quality threshold for cut-right', 'default': '20'}),
                "disable_quality": ('BOOLEAN', {'description': 'Disable quality filtering', 'default': False}),
                "qualified_qual": ('STRING', {'description': 'Base is qualified if quality >= N', 'default': '15'}),
                "unqualified_percent": ('STRING', {'description': 'Max % of unqualified bases', 'default': '40.0'}),
                "avg_qual": ('STRING', {'description': 'Minimum average quality (0=disabled)', 'default': '0'}),
                "n_base_limit": ('STRING', {'description': 'Max number of N bases', 'default': '5'}),
                "min_length": ('STRING', {'description': 'Minimum read length', 'default': '15'}),
                "max_length": ('STRING', {'description': 'Maximum read length (0=unlimited)', 'default': '0'}),
                "complexity": ('BOOLEAN', {'description': 'Enable low complexity filter', 'default': False}),
                "threads": ('STRING', {'description': 'Number of threads', 'default': '1'}),
                "batch_size": ('STRING', {'description': 'Reads per batch for threading', 'default': '10000'}),
                "offset": ('STRING', {'description': 'Quality offset', 'default': '33'}),
                "preset": ('STRING', {'description': 'Apply preset configuration (strict|lenient)', 'default': ''}),
                "stats_json": ('STRING', {'description': 'Write detailed stats to JSON file', 'default': ''}),
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
