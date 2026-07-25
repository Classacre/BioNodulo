"""MUMmer4 4.0.1 maximal exact-match discovery with ``mummer``."""

from __future__ import annotations

from typing import Any

from .adapter import (
    Mummer4CommandNode,
    add_flag,
    path_list,
    path_value,
    validate_choice,
    validate_int,
)


class Mummer4MummerNode(Mummer4CommandNode):
    """Find maximal matches between one reference and one or more queries."""

    NODE_ID = "mummer4_mummer"
    DISPLAY_NAME = "MUMmer4 Mummer"
    DESCRIPTION = "Find maximal exact matches between nucleotide FASTA sequences with mummer."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "MUMmer4",
        "mummer",
        "maximal exact match",
        "MUM",
        "MEM",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("alignment",)
    OUTPUT_FILENAMES = ("matches.txt",)
    STDOUT_OUTPUT_INDEX = 0
    REQUIRED_EXECUTABLES = ["mummer"]
    REQUIRED_PATH_INPUTS = ("reference_sequence",)
    REQUIRED_PATH_LIST_INPUTS = ("query_sequence",)
    UPSTREAM_SOURCE = "src/essaMEM/mummer.cpp"
    SOURCE_PATHS = (UPSTREAM_SOURCE, "src/essaMEM/sparseSA.cpp", "README.md")
    EXIT_SEMANTICS = (
        "mummer exits 1 for missing inputs, unknown options, non-positive index threads, "
        "-k outside maxmatch mode, or mutually exclusive -b/-r strand flags. Its native "
        "stdout is a headered, whitespace-aligned match list rather than TSV."
    )

    MATCH_MODES = ("mumreference", "mum", "maxmatch")
    STRANDS = ("forward", "both", "reverse")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference_sequence": ("FASTA", {"description": "Reference FASTA"}),
                "query_sequence": (
                    "FASTA_LIST",
                    {"multiple": True, "description": "One or more query FASTA files"},
                ),
            },
            "optional": {
                "match_mode": ("STRING", {"default": "mumreference", "options": list(cls.MATCH_MODES)}),
                "min_length": ("INT", {"default": 20, "min": 1}),
                "strand": ("STRING", {"default": "forward", "options": list(cls.STRANDS)}),
                "force_four_column": ("BOOLEAN", {"default": False}),
                "nucleotides_only": ("BOOLEAN", {"default": False}),
                "print_query_length": ("BOOLEAN", {"default": False}),
                "print_substring": ("BOOLEAN", {"default": False}),
                "reverse_positions": ("BOOLEAN", {"default": False}),
                "sparse_index": ("INT", {"default": 1, "min": 1, "advanced": True}),
                "threads": ("INT", {"default": 1, "min": 1}),
                "query_threads": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "max_chunk": ("INT", {"default": 50000, "min": 1, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key, value, choices in (
            ("match_mode", inputs.get("match_mode", "mumreference"), cls.MATCH_MODES),
            ("strand", inputs.get("strand", "forward"), cls.STRANDS),
        ):
            validation = validate_choice(value, key, choices)
            if validation is not True:
                return validation
        for key, default, minimum in (
            ("min_length", 20, 1),
            ("sparse_index", 1, 1),
            ("threads", 1, 1),
            ("query_threads", 0, 0),
            ("max_chunk", 50000, 1),
        ):
            validation = validate_int(inputs.get(key, default), key, minimum=minimum)
            if validation is not True:
                return validation
        if inputs.get("sparse_index", 1) != 1 and inputs.get("match_mode", "mumreference") != "maxmatch":
            return "Input 'sparse_index' may differ from 1 only when 'match_mode' is 'maxmatch'"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "mummer")
        match_mode = str(inputs.get("match_mode", "mumreference"))
        if match_mode != "mumreference":
            command.append(f"-{match_mode}")
        command.extend(["-l", str(inputs.get("min_length", 20))])
        strand = str(inputs.get("strand", "forward"))
        if strand == "both":
            command.append("-b")
        elif strand == "reverse":
            command.append("-r")
        add_flag(command, "-F", inputs.get("force_four_column"))
        add_flag(command, "-n", inputs.get("nucleotides_only"))
        add_flag(command, "-L", inputs.get("print_query_length"))
        add_flag(command, "-s", inputs.get("print_substring"))
        add_flag(command, "-c", inputs.get("reverse_positions"))
        sparse_index = int(inputs.get("sparse_index", 1))
        if sparse_index != 1:
            command.extend(["-k", str(sparse_index)])
        command.extend(["-threads", str(inputs.get("threads", 1))])
        query_threads = int(inputs.get("query_threads", 0))
        if query_threads:
            command.extend(["-qthreads", str(query_threads)])
        max_chunk = int(inputs.get("max_chunk", 50000))
        if max_chunk != 50000:
            command.extend(["-max-chunk", str(max_chunk)])
        command.append(path_value(inputs.get("reference_sequence")))
        command.extend(path_list(inputs.get("query_sequence")))
        return command
