"""BEDTools flank node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsFlankNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_flankbed"
    DISPLAY_NAME = "BEDTools Flank"
    DESCRIPTION = "Create intervals flanking each input feature within genome bounds"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "flank", "flankbed", "upstream", "downstream"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("flanks",)
    OUTPUT_FILENAMES = ("flanks.bed",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/flank.html"
    UPSTREAM_SOURCE = "src/flankBed/flankBed.cpp"
    REQUIRED_PATH_INPUTS = ("input", "genome")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input": ("BED", {}), "genome": ("TSV", {})},
            "optional": {
                "addition_mode": ("STRING", {"default": "b", "options": ["b", "lr"]}),
                "both": ("FLOAT", {"default": 1, "min": 0}),
                "left": ("FLOAT", {"default": 0, "min": 0}),
                "right": ("FLOAT", {"default": 0, "min": 0}),
                "pct": ("BOOLEAN", {"default": False}),
                "strand": ("BOOLEAN", {"default": False}),
                "header": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        mode = str(inputs.get("addition_mode", "b"))
        if mode not in ("b", "lr"):
            return "addition_mode must be b or lr"
        keys = ("both",) if mode == "b" else ("left", "right")
        for key in keys:
            value = inputs.get(key, 0)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) < 0:
                return f"Input '{key}' must be a non-negative number"
            if not inputs.get("pct") and not float(value).is_integer():
                return f"Input '{key}' must be an integer unless pct=True"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "flank", "-i", str(inputs["input"]), "-g", str(inputs["genome"]))
        if inputs.get("addition_mode", "b") == "b":
            command.extend(["-b", str(inputs.get("both", 1))])
        else:
            command.extend(["-l", str(inputs.get("left", 0)), "-r", str(inputs.get("right", 0))])
        if inputs.get("strand"):
            command.append("-s")
        if inputs.get("pct"):
            command.append("-pct")
        if inputs.get("header"):
            command.append("-header")
        return command
