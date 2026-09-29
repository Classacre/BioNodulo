"""Focused owner for ``seqfu_count``.

Real syntax, read from ``seqfu count --help`` in the pinned image::

    Usage: count [options] [<inputfile> ...]

Output is written to **stdout**, one tab-separated row per input with no header::

    <file>\t<count>\t<SE|PE>

so the node captures stdout (``STDOUT_OUTPUT_INDEX = 0``) into ``counts.tsv``.
"""

from __future__ import annotations

from typing import Any, ClassVar

from .adapter import BIONODULO_BUILTIN_ALIAS, SeqfuBase, _path_values


class SeqfuCountNode(SeqfuBase):
    NODE_ID = "seqfu_count"
    DISPLAY_NAME = "SeqFu Count"
    DESCRIPTION = "Count sequences in FASTA/FASTQ files, pair-end aware, with SeqFu count."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "seqfu",
        "count",
        "read count",
        "sequence count",
        "fasta count",
        "fastq count",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("counts",)
    OUTPUT_FILENAMES = ("counts.tsv",)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = "https://telatin.github.io/seqfu2/tools/count.html"

    SORT_MODES: ClassVar[tuple[str, ...]] = ("input", "name", "counts", "none")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    "FASTQ_LIST",
                    {"multiple": True, "description": "One or more FASTA/FASTQ files"},
                ),
            },
            "optional": {
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
                "basename": ("BOOLEAN", {"default": False, "description": "Print only file basenames"}),
                "unpair": (
                    "BOOLEAN",
                    {"default": False, "description": "Print separate records for paired-end files"},
                ),
                "reverse_sort": ("BOOLEAN", {"default": False, "description": "Reverse the sort order"}),
                "sort_mode": (
                    "STRING",
                    {"default": "input", "options": list(cls.SORT_MODES)},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        threads = inputs.get("threads", 4)
        if isinstance(threads, bool) or not isinstance(threads, int) or threads < 1:
            return "threads must be a positive integer"
        sort_mode = str(inputs.get("sort_mode", "input"))
        if sort_mode not in cls.SORT_MODES:
            return f"sort_mode must be one of: {', '.join(cls.SORT_MODES)}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ["seqfu", "count", "--threads", str(inputs.get("threads", 4))]
        if inputs.get("basename"):
            command.append("--basename")
        if inputs.get("unpair"):
            command.append("--unpair")
        sort_mode = str(inputs.get("sort_mode", "input"))
        if sort_mode != "input":
            command.extend(["--sort", sort_mode])
        if inputs.get("reverse_sort"):
            command.append("--reverse-sort")
        command.extend(_path_values(inputs.get("input")))
        return command
