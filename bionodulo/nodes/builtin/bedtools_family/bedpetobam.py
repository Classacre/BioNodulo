"""BEDTools bedpetobam node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsBedpeToBamNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_bedpetobam"
    DISPLAY_NAME = "BEDTools BEDPE to BAM"
    DESCRIPTION = "Convert BEDPE records to unsorted compressed BAM"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "bedpetobam", "bedpe to bam", "paired-end"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("paired_bam",)
    OUTPUT_FILENAMES = ("paired.bam",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/bedpetobam.html"
    UPSTREAM_SOURCE = "src/bedpeToBam/bedpeToBam.cpp"
    REQUIRED_PATH_INPUTS = ("input", "genome")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input": ("BED", {}), "genome": ("TSV", {})},
            "optional": {"mapq": ("INT", {"default": 255, "min": 0, "max": 255})},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        mapq = inputs.get("mapq", 255)
        validation = cls.validate_int(mapq, "mapq", minimum=0)
        if validation is not True:
            return validation
        return True if int(mapq) <= 255 else "Input 'mapq' must be at most 255"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return cls.checked_command(
            inputs,
            "bedtools", "bedpetobam", "-i", str(inputs["input"]),
            "-g", str(inputs["genome"]), "-mapq", str(inputs.get("mapq", 255)),
        )
