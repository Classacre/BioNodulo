"""BEDTools complement node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsComplementNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_complementbed"
    DISPLAY_NAME = "BEDTools Complement"
    DESCRIPTION = "Report genome intervals absent from a sorted interval file"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "complement", "complementbed", "genome gaps"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("complement",)
    OUTPUT_FILENAMES = ("complement.bed",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/complement.html"
    UPSTREAM_SOURCE = "src/complementFile/complementFile.cpp"
    REQUIRED_PATH_INPUTS = ("input", "genome")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input": ("BED", {"description": "Sorted intervals"}), "genome": ("TSV", {})},
            "optional": {"limit": ("BOOLEAN", {"default": False})},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "complement", "-i", str(inputs["input"]), "-g", str(inputs["genome"]))
        if inputs.get("limit"):
            command.append("-L")
        return command
