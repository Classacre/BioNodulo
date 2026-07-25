"""BEDTools igv node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsBedToIgvNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_bedtoigv"
    DISPLAY_NAME = "BEDTools BED to IGV"
    DESCRIPTION = "Create an IGV batch script for interval snapshots"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "igv", "bedtoigv", "IGV snapshots"]
    RETURN_TYPES = ("TEXT",)
    RETURN_NAMES = ("igv_batch_script",)
    OUTPUT_FILENAMES = ("igv_batch_script.txt",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/igv.html"
    UPSTREAM_SOURCE = "src/bedToIgv/bedToIgv.cpp"
    REQUIRED_PATH_INPUTS = ("input",)
    SORT_MODES = ("", "base", "position", "strand", "quality", "sample", "readGroup")
    IMAGE_TYPES = ("png", "eps", "svg")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input": ("FILE", {})},
            "optional": {
                "path": ("STRING", {"default": "./"}),
                "session": ("FILE", {"default": ""}),
                "sort": ("STRING", {"default": "", "options": list(cls.SORT_MODES)}),
                "clps": ("BOOLEAN", {"default": False}),
                "name": ("BOOLEAN", {"default": False}),
                "slop": ("INT", {"default": 0, "min": 0}),
                "img": ("STRING", {"default": "png", "options": list(cls.IMAGE_TYPES)}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if inputs.get("session") not in (None, ""):
            validation = cls.require_path(inputs, "session")
            if validation is not True:
                return validation
        for key, choices, default in (("sort", cls.SORT_MODES, ""), ("img", cls.IMAGE_TYPES, "png")):
            validation = cls.validate_choice(inputs.get(key, default), choices, key)
            if validation is not True:
                return validation
        return cls.validate_int(inputs.get("slop", 0), "slop", minimum=0)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "igv", "-i", str(inputs["input"]))
        command.extend(["-path", str(inputs.get("path", "./"))])
        if inputs.get("session"):
            command.extend(["-sess", str(inputs["session"])])
        if inputs.get("sort"):
            command.extend(["-sort", str(inputs["sort"])])
        if inputs.get("clps"):
            command.append("-clps")
        if inputs.get("name"):
            command.append("-name")
        command.extend(["-slop", str(inputs.get("slop", 0)), "-img", str(inputs.get("img", "png"))])
        return command
