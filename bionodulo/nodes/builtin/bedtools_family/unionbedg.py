"""BEDTools unionbedg node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsUnionBedGraphNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_unionbedgraph"
    DISPLAY_NAME = "BEDTools Union BedGraph"
    DESCRIPTION = "Combine sorted non-overlapping BedGraph files into common intervals"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "unionbedg", "unionbedgraph", "coverage tracks"]
    RETURN_TYPES = ("BEDGRAPH",)
    RETURN_NAMES = ("union_bedgraph",)
    OUTPUT_FILENAMES = ("union.bedgraph",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/unionbedg.html"
    UPSTREAM_SOURCE = "src/unionBedGraphs/unionBedGraphs.cpp"
    REQUIRED_PATH_LIST_INPUTS = ("inputs",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"inputs": ("BEDGRAPH_LIST", {})},
            "optional": {
                "names": ("STRING_LIST", {}),
                "header": ("BOOLEAN", {"default": False}),
                "filler": ("STRING", {"default": "0"}),
                "empty": ("BOOLEAN", {"default": False}),
                "genome": ("TSV", {"default": ""}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        files = cls.path_list(inputs.get("inputs"))
        if len(files) < 2:
            return "unionbedg requires at least two input files"
        names = [str(name) for name in inputs.get("names", [])]
        if names and len(names) != len(files):
            return "Input 'names' must contain exactly one label per BedGraph file"
        if inputs.get("empty"):
            return cls.require_path(inputs, "genome")
        if inputs.get("genome"):
            return "genome is only valid with empty=True"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "unionbedg")
        if inputs.get("header"):
            command.append("-header")
        command.extend(["-filler", str(inputs.get("filler", "0"))])
        if inputs.get("empty"):
            command.extend(["-empty", "-g", str(inputs["genome"])])
        command.extend(["-i", *cls.path_list(inputs["inputs"])])
        names = [str(name) for name in inputs.get("names", [])]
        if names:
            command.extend(["-names", *names])
        return command
