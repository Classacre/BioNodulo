"""BEDTools spacing node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsSpacingNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_spacingbed"
    DISPLAY_NAME = "BEDTools Spacing"
    DESCRIPTION = "Append the distance from each sorted interval to its predecessor"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "spacing", "spacingbed", "adjacent intervals"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("spacing",)
    OUTPUT_FILENAMES = ("spacing.tsv",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/spacing.html"
    UPSTREAM_SOURCE = "src/spacingFile/spacingFile.cpp"
    REQUIRED_PATH_INPUTS = ("input",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {"required": {"input": ("FILE", {"description": "Chromosome/start-sorted intervals"})}, "optional": {}, "hidden": {"output": ("STRING", {})}}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return cls.checked_command(inputs, "bedtools", "spacing", "-i", str(inputs["input"]))
