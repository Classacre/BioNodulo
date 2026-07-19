"""BEDTools reldist node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsRelativeDistanceNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_reldistbed"
    DISPLAY_NAME = "BEDTools Relative Distance"
    DESCRIPTION = "Calculate relative distances between two interval sets"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "reldist", "reldistbed", "relative distance"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("relative_distance",)
    OUTPUT_FILENAMES = ("relative_distance.tsv",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/reldist.html"
    UPSTREAM_SOURCE = "src/reldist/reldist.cpp"
    REQUIRED_PATH_INPUTS = ("inputA", "inputB")
    CITATION_DOIS = ["10.1093/bioinformatics/btq033", "10.1371/journal.pcbi.1002529"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btq033", "https://doi.org/10.1371/journal.pcbi.1002529"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"inputA": ("BED", {}), "inputB": ("BED", {})},
            "optional": {"detail": ("BOOLEAN", {"default": False})},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "reldist", "-a", str(inputs["inputA"]), "-b", str(inputs["inputB"]))
        if inputs.get("detail"):
            command.append("-detail")
        return command
