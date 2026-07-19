"""MUMmer4 4.0.1 tabular coordinate reporting."""

from __future__ import annotations

from typing import Any

from .adapter import (
    Mummer4CommandNode,
    add_flag,
    path_value,
    validate_choice,
    validate_int,
    validate_number,
)


class Mummer4ShowCoordsNode(Mummer4CommandNode):
    """Render delta alignments as source-native tab-delimited coordinates."""

    NODE_ID = "mummer4_show_coords"
    DISPLAY_NAME = "MUMmer4 Show Coordinates"
    DESCRIPTION = "Convert a delta alignment to tab-delimited coordinates on stdout."
    SEARCH_ALIASES = ["BioNodulo builtin", "MUMmer4", "show-coords", "alignment coordinates"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("coordinates",)
    OUTPUT_FILENAMES = ("coordinates.tsv",)
    STDOUT_OUTPUT_INDEX = 0
    REQUIRED_EXECUTABLES = ["show-coords"]
    REQUIRED_PATH_INPUTS = ("delta",)
    UPSTREAM_SOURCE = "src/tigr/show-coords.cc"
    SORTS = ("none", "query", "reference")
    ANNOTATIONS = ("none", "overlaps", "warnings")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"delta": ("FILE", {"description": "Nucmer or promer delta alignment"})},
            "optional": {
                "brief": ("BOOLEAN", {"default": False}),
                "coverage": ("BOOLEAN", {"default": False}),
                "direction": ("BOOLEAN", {"default": False}),
                "include_header": ("BOOLEAN", {"default": False}),
                "min_identity": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 100.0}),
                "knockout": ("BOOLEAN", {"default": False, "description": "Promer frame-overlap knockout"}),
                "sequence_lengths": ("BOOLEAN", {"default": False}),
                "min_alignment_length": ("INT", {"default": 0, "min": 0}),
                "annotation": ("STRING", {"default": "none", "options": list(cls.ANNOTATIONS)}),
                "sort": ("STRING", {"default": "none", "options": list(cls.SORTS)}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key, value, choices in (
            ("annotation", inputs.get("annotation", "none"), cls.ANNOTATIONS),
            ("sort", inputs.get("sort", "none"), cls.SORTS),
        ):
            validation = validate_choice(value, key, choices)
            if validation is not True:
                return validation
        validation = validate_number(inputs.get("min_identity", 0.0), "min_identity", minimum=0, maximum=100)
        if validation is not True:
            return validation
        return validate_int(inputs.get("min_alignment_length", 0), "min_alignment_length", minimum=0)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "show-coords")
        add_flag(command, "-b", inputs.get("brief"))
        add_flag(command, "-c", inputs.get("coverage"))
        add_flag(command, "-d", inputs.get("direction"))
        if not inputs.get("include_header", False):
            command.append("-H")
        command.extend(["-I", str(inputs.get("min_identity", 0.0))])
        add_flag(command, "-k", inputs.get("knockout"))
        add_flag(command, "-l", inputs.get("sequence_lengths"))
        command.extend(["-L", str(inputs.get("min_alignment_length", 0))])
        annotation = str(inputs.get("annotation", "none"))
        if annotation == "overlaps":
            command.append("-o")
        elif annotation == "warnings":
            command.append("-w")
        sort = str(inputs.get("sort", "none"))
        if sort == "query":
            command.append("-q")
        elif sort == "reference":
            command.append("-r")
        command.extend(["-T", path_value(inputs.get("delta"))])
        return command
