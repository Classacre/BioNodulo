"""Focused owner for ``seqfu_list``.

Real syntax, read from ``seqfu list --help`` in the pinned image::

    Usage: list [options] <LIST> <FASTQ>...
    Classic mode: print sequences from <FASTQ> whose names appear in <LIST>.

Matching records are written to **stdout** in input order, preserving the input
record format (FASTA in, FASTA out). ``--strict`` makes a missing listed name a
non-zero exit rather than a silent omission.
"""

from __future__ import annotations

from typing import Any

from .adapter import BIONODULO_BUILTIN_ALIAS, SeqfuBase, _path_values


class SeqfuListNode(SeqfuBase):
    NODE_ID = "seqfu_list"
    DISPLAY_NAME = "SeqFu List"
    DESCRIPTION = (
        "Select FASTA/FASTQ records whose names appear in a list file with SeqFu list, "
        "preserving input order and record format."
    )
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "seqfu",
        "list",
        "select by name",
        "subset sequences",
        "filter by id",
        "sequence names",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("selected",)
    OUTPUT_FILENAMES = ("selected.fasta",)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = "https://telatin.github.io/seqfu2/tools/list.html"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    "FASTQ_LIST",
                    {"multiple": True, "description": "One or more FASTA/FASTQ files to select from"},
                ),
                "names": (
                    "FILE",
                    {
                        "description": (
                            "List file of sequence names to keep (one per line; leading "
                            "'>'/'@' and '#' comments are allowed)"
                        )
                    },
                ),
            },
            "optional": {
                "partial_match": (
                    "BOOLEAN",
                    {"default": False, "description": "Match list entries as substrings of sequence names"},
                ),
                "with_comments": (
                    "BOOLEAN",
                    {"default": False, "description": "Include comments when matching sequence names"},
                ),
                "strict": (
                    "BOOLEAN",
                    {"default": False, "description": "Fail if any listed name is not found"},
                ),
                "min_len": ("INT", {"default": 1, "min": 1, "description": "Skip list entries shorter than this"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        min_len = inputs.get("min_len", 1)
        if isinstance(min_len, bool) or not isinstance(min_len, int) or min_len < 1:
            return "min_len must be an integer of at least 1"
        names = _path_values(inputs.get("names"))
        if len(names) != 1:
            return "names must be exactly one list file"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ["seqfu", "list"]
        if inputs.get("with_comments"):
            command.append("--with-comments")
        if inputs.get("partial_match"):
            command.append("--partial-match")
        if inputs.get("strict"):
            command.append("--strict")
        min_len = inputs.get("min_len", 1)
        if int(min_len) != 1:
            command.extend(["--min-len", str(min_len)])
        command.extend(_path_values(inputs.get("names")))
        command.extend(_path_values(inputs.get("input")))
        return command
