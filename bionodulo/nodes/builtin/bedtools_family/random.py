"""BEDTools random node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsRandomNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_randombed"
    DISPLAY_NAME = "BEDTools Random"
    DESCRIPTION = "Generate random BED6 intervals across a genome"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "random", "randombed", "random intervals"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("random_intervals",)
    OUTPUT_FILENAMES = ("random.bed",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/random.html"
    UPSTREAM_SOURCE = "src/randomBed/randomBed.cpp"
    REQUIRED_PATH_INPUTS = ("genome",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"genome": ("TSV", {})},
            "optional": {
                "length": ("INT", {"default": 100, "min": 1}),
                "intervals": ("INT", {"default": 1000000, "min": 1}),
                "seed": ("INT", {"default": ""}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key, default in (("length", 100), ("intervals", 1000000)):
            validation = cls.validate_int(inputs.get(key, default), key, minimum=1)
            if validation is not True:
                return validation
        return cls.validate_int(inputs.get("seed"), "seed")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(
            inputs, "bedtools", "random", "-g", str(inputs["genome"]),
            "-l", str(inputs.get("length", 100)), "-n", str(inputs.get("intervals", 1000000)),
        )
        cls.optional_value(command, "-seed", inputs.get("seed"))
        return command
