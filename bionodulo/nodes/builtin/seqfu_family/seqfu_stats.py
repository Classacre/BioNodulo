"""Focused owner for ``seqfu_stats``.

Real syntax, read from ``seqfu stats --help`` in the pinned image::

    Usage: stats [options] [<inputfile> ...]

Output is a tab-separated table written to **stdout**, with a header row::

    File  #Seq  Total bp  Avg  N50  N75  N90  auN  Min  Max

so the node captures stdout (``STDOUT_OUTPUT_INDEX = 0``) into ``stats.tsv``.
"""

from __future__ import annotations

from typing import Any, ClassVar

from .adapter import BIONODULO_BUILTIN_ALIAS, SeqfuBase, _path_values


class SeqfuStatsNode(SeqfuBase):
    NODE_ID = "seqfu_stats"
    DISPLAY_NAME = "SeqFu Stats"
    DESCRIPTION = (
        "Report FASTA/FASTQ sequence counts, total bases, length summaries and N50 "
        "with SeqFu stats."
    )
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "seqfu",
        "stats",
        "fasta statistics",
        "fastq statistics",
        "n50",
        "sequence length",
        "total bases",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("stats",)
    OUTPUT_FILENAMES = ("stats.tsv",)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = "https://telatin.github.io/seqfu2/tools/stats.html"

    SORT_KEYS: ClassVar[tuple[str, ...]] = ("filename", "counts", "n50", "tot", "avg", "min", "max")

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
                "gc": ("BOOLEAN", {"default": False, "description": "Also print %GC"}),
                "index": (
                    "BOOLEAN",
                    {"default": False, "description": "Also print contig index (L50, L90)"},
                ),
                "csv": (
                    "BOOLEAN",
                    {"default": False, "description": "Separate columns with commas instead of tabs"},
                ),
                "noheader": ("BOOLEAN", {"default": False, "description": "Do not print a header row"}),
                "basename": ("BOOLEAN", {"default": False, "description": "Print only file basenames"}),
                "reverse": ("BOOLEAN", {"default": False, "description": "Reverse the sort order"}),
                "sort_by": (
                    "STRING",
                    {"default": "none", "options": ["none", *cls.SORT_KEYS]},
                ),
                "precision": ("INT", {"default": 2, "min": 0, "max": 10}),
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
        precision = inputs.get("precision", 2)
        if isinstance(precision, bool) or not isinstance(precision, int) or precision < 0:
            return "precision must be a non-negative integer"
        sort_by = str(inputs.get("sort_by", "none"))
        if sort_by not in ("none", *cls.SORT_KEYS):
            return f"sort_by must be one of: none, {', '.join(cls.SORT_KEYS)}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ["seqfu", "stats", "--threads", str(inputs.get("threads", 4))]
        for flag, key in (
            ("--gc", "gc"),
            ("--index", "index"),
            ("--csv", "csv"),
            ("--noheader", "noheader"),
            ("--basename", "basename"),
            ("--reverse", "reverse"),
        ):
            if inputs.get(key):
                command.append(flag)
        sort_by = str(inputs.get("sort_by", "none"))
        if sort_by != "none":
            command.extend(["--sort-by", sort_by])
        command.extend(["--precision", str(inputs.get("precision", 2))])
        command.extend(_path_values(inputs.get("input")))
        return command
