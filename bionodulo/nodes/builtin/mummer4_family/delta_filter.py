"""MUMmer4 4.0.1 delta alignment filtering."""

from __future__ import annotations

from typing import Any

from .adapter import (
    Mummer4CommandNode,
    path_value,
    validate_choice,
    validate_int,
    validate_number,
)


class Mummer4DeltaFilterNode(Mummer4CommandNode):
    """Filter a delta stream by identity, length, uniqueness, and mapping mode."""

    NODE_ID = "mummer4_delta_filter"
    DISPLAY_NAME = "MUMmer4 Delta Filter"
    DESCRIPTION = "Filter nucmer or promer delta alignments and capture the native delta stream."
    SEARCH_ALIASES = ["BioNodulo builtin", "MUMmer4", "delta-filter", "filter delta"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("filtered_delta",)
    OUTPUT_FILENAMES = ("filtered.delta",)
    STDOUT_OUTPUT_INDEX = 0
    REQUIRED_EXECUTABLES = ["delta-filter"]
    REQUIRED_PATH_INPUTS = ("delta",)
    UPSTREAM_SOURCE = "src/tigr/delta-filter.cc"
    MODES = ("none", "query", "reference", "global", "many_to_many", "one_to_one")
    MODE_FLAGS = {
        "query": "-q",
        "reference": "-r",
        "global": "-g",
        "many_to_many": "-m",
        "one_to_one": "-1",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"delta": ("FILE", {"description": "Nucmer or promer delta alignment"})},
            "optional": {
                "mode": ("STRING", {"default": "none", "options": list(cls.MODES)}),
                "min_identity": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 100.0}),
                "min_length": ("INT", {"default": 0, "min": 0}),
                "min_uniqueness": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 100.0}),
                "max_overlap": ("FLOAT", {"default": 100.0, "min": 0.0, "max": 100.0}),
                "epsilon": ("FLOAT", {"default": None, "description": "Negligible LIS score threshold"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_choice(inputs.get("mode", "none"), "mode", cls.MODES)
        if validation is not True:
            return validation
        validation = validate_int(inputs.get("min_length", 0), "min_length", minimum=0)
        if validation is not True:
            return validation
        for key, default in (
            ("min_identity", 0.0),
            ("min_uniqueness", 0.0),
            ("max_overlap", 100.0),
        ):
            validation = validate_number(inputs.get(key, default), key, minimum=0, maximum=100)
            if validation is not True:
                return validation
        if inputs.get("epsilon") is not None:
            return validate_number(inputs["epsilon"], "epsilon")
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "delta-filter")
        if inputs.get("epsilon") is not None:
            command.extend(["-e", str(inputs["epsilon"])])
        command.extend(
            [
                "-i",
                str(inputs.get("min_identity", 0.0)),
                "-l",
                str(inputs.get("min_length", 0)),
                "-u",
                str(inputs.get("min_uniqueness", 0.0)),
            ]
        )
        mode = str(inputs.get("mode", "none"))
        if mode != "none":
            command.append(cls.MODE_FLAGS[mode])
        command.extend(["-o", str(inputs.get("max_overlap", 100.0)), path_value(inputs.get("delta"))])
        return command
