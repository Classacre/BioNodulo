"""BEDTools bedtobam node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsBedToBamNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_bedtobam"
    DISPLAY_NAME = "BEDTools BED to BAM"
    DESCRIPTION = "Convert BED records to unsorted compressed BAM"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "bedtobam", "bed to bam", "bed12"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("converted_bam",)
    OUTPUT_FILENAMES = ("converted.bam",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/bedtobam.html"
    UPSTREAM_SOURCE = "src/bedToBam/bedToBam.cpp"
    REQUIRED_PATH_INPUTS = ("input", "genome")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input": ("BED", {}), "genome": ("TSV", {})},
            "optional": {
                "bed12": ("BOOLEAN", {"default": False}),
                "mapq": ("INT", {"default": 255, "min": 0, "max": 255}),
            },
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
        command = cls.checked_command(inputs, "bedtools", "bedtobam", "-i", str(inputs["input"]), "-g", str(inputs["genome"]))
        if inputs.get("bed12"):
            command.append("-bed12")
        command.extend(["-mapq", str(inputs.get("mapq", 255))])
        return command
