"""BEDTools cluster node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsClusterNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_clusterbed"
    DISPLAY_NAME = "BEDTools Cluster"
    DESCRIPTION = "Append cluster IDs to sorted overlapping or nearby intervals"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "cluster", "clusterbed", "interval clusters"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("clustered",)
    OUTPUT_FILENAMES = ("clustered.bed",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/cluster.html"
    UPSTREAM_SOURCE = "src/clusterBed/clusterMain.cpp"
    REQUIRED_PATH_INPUTS = ("inputA",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"inputA": ("BED", {"description": "Chromosome/start-sorted intervals"})},
            "optional": {"strand": ("BOOLEAN", {"default": False}), "distance": ("INT", {"default": 0, "min": 0})},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        return cls.validate_int(inputs.get("distance", 0), "distance", minimum=0)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "cluster", "-i", str(inputs["inputA"]))
        if inputs.get("strand"):
            command.append("-s")
        command.extend(["-d", str(inputs.get("distance", 0))])
        return command
