"""BEDTools makewindows node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsMakeWindowsNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_makewindowsbed"
    DISPLAY_NAME = "BEDTools Make Windows"
    DESCRIPTION = "Create fixed-size, sliding, or fixed-count windows over a genome or BED file"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "makewindows", "makewindowsbed", "sliding windows"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("windows",)
    OUTPUT_FILENAMES = ("windows.bed",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/makewindows.html"
    UPSTREAM_SOURCE = "src/windowMaker/windowMaker.cpp"
    SOURCES = ("bed", "genome")
    ACTIONS = ("windowsize", "number")
    NAMES = ("", "src", "winnum", "srcwinnum")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "type": ("STRING", {"default": "bed", "options": list(cls.SOURCES)}),
                "action": ("STRING", {"default": "windowsize", "options": list(cls.ACTIONS)}),
            },
            "optional": {
                "input": ("BED", {"default": ""}),
                "genome": ("TSV", {"default": ""}),
                "windowsize": ("INT", {"default": 1, "min": 1}),
                "step_size": ("INT", {"default": "", "min": 1}),
                "number": ("INT", {"default": 1, "min": 1}),
                "sourcename": ("STRING", {"default": "", "options": list(cls.NAMES)}),
                "reverse": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        source = str(inputs.get("type", "bed"))
        action = str(inputs.get("action", "windowsize"))
        for key, value, choices in (("type", source, cls.SOURCES), ("action", action, cls.ACTIONS), ("sourcename", inputs.get("sourcename", ""), cls.NAMES)):
            validation = cls.validate_choice(value, choices, key)
            if validation is not True:
                return validation
        required_key = "input" if source == "bed" else "genome"
        validation = cls.require_path(inputs, required_key)
        if validation is not True:
            return validation
        other_key = "genome" if source == "bed" else "input"
        if inputs.get(other_key):
            return f"Input '{other_key}' is not valid when type={source}"
        size_key = "number" if action == "number" else "windowsize"
        validation = cls.validate_int(inputs.get(size_key, 1), size_key, minimum=1)
        if validation is not True:
            return validation
        if action == "number" and inputs.get("step_size") not in (None, ""):
            return "step_size is only valid with windowsize action"
        return cls.validate_int(inputs.get("step_size"), "step_size", minimum=1)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "makewindows")
        if inputs.get("type", "bed") == "genome":
            command.extend(["-g", str(inputs["genome"])])
        else:
            command.extend(["-b", str(inputs["input"])])
        if inputs.get("action", "windowsize") == "number":
            command.extend(["-n", str(inputs.get("number", 1))])
        else:
            command.extend(["-w", str(inputs.get("windowsize", 1))])
            cls.optional_value(command, "-s", inputs.get("step_size"))
        if inputs.get("sourcename"):
            command.extend(["-i", str(inputs["sourcename"])])
        if inputs.get("reverse"):
            command.append("-reverse")
        return command
