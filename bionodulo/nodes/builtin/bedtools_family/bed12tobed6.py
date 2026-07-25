"""BEDTools bed12tobed6 node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsBed12ToBed6Node(BEDToolsStdoutNode):
    NODE_ID = "bedtools_bed12tobed6"
    DISPLAY_NAME = "BEDTools BED12 to BED6"
    DESCRIPTION = "Expand BED12 blocks into BED6 records"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "bed12tobed6", "bed12 to bed6", "exons"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("bed6",)
    OUTPUT_FILENAMES = ("bed6.bed",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/bed12tobed6.html"
    UPSTREAM_SOURCE = "src/bed12ToBed6/bed12ToBed6.cpp"
    REQUIRED_PATH_INPUTS = ("input",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input": ("BED", {"description": "BED12 records"})},
            "optional": {"block_number": ("BOOLEAN", {"default": False})},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "bed12tobed6")
        if inputs.get("block_number"):
            command.append("-n")
        command.extend(["-i", str(inputs["input"])])
        return command
