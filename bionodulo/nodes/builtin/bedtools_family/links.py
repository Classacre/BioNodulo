"""BEDTools links node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsLinksNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_links"
    DISPLAY_NAME = "BEDTools LinksBed"
    DESCRIPTION = "Create an HTML page of UCSC Genome Browser interval links"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "links", "linksbed", "UCSC links"]
    RETURN_TYPES = ("HTML",)
    RETURN_NAMES = ("links_html",)
    OUTPUT_FILENAMES = ("links.html",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/links.html"
    UPSTREAM_SOURCE = "src/linksBed/linksBed.cpp"
    REQUIRED_PATH_INPUTS = ("input",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input": ("FILE", {})},
            "optional": {
                "basename": ("STRING", {"default": "http://genome.ucsc.edu"}),
                "org": ("STRING", {"default": "human"}),
                "db": ("STRING", {"default": "hg18"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key, default in (("basename", "http://genome.ucsc.edu"), ("org", "human"), ("db", "hg18")):
            if not str(inputs.get(key, default)).strip():
                return f"Input '{key}' must be non-empty"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return cls.checked_command(
            inputs,
            "bedtools", "links", "-base", str(inputs.get("basename", "http://genome.ucsc.edu")),
            "-org", str(inputs.get("org", "human")), "-db", str(inputs.get("db", "hg18")),
            "-i", str(inputs["input"]),
        )
