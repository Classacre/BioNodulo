"""BEDTools subtract node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsSubtractNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_subtractbed"
    DISPLAY_NAME = "BEDTools Subtract"
    DESCRIPTION = "Subtract overlapping B bases or records from A intervals"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "subtract", "subtractbed", "blacklist"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("subtracted",)
    OUTPUT_FILENAMES = ("subtracted.bed",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/subtract.html"
    UPSTREAM_SOURCE = "src/subtractFile/subtractFile.cpp"
    REQUIRED_PATH_INPUTS = ("inputA", "inputB")
    REMOVE_MODES = ("", "remove_feature", "remove_feature_sum")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"inputA": ("BED", {}), "inputB": ("BED", {})},
            "optional": {
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1}),
                "overlap_b": ("FLOAT", {"default": "", "min": 0, "max": 1}),
                "reciprocal": ("BOOLEAN", {"default": False}),
                "either_fraction": ("BOOLEAN", {"default": False}),
                "remove_if_overlap": ("STRING", {"default": "", "options": list(cls.REMOVE_MODES)}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if "removeIfOverlap" in inputs:
            return "removeIfOverlap is stale; use remove_if_overlap"
        for key, choices in (("strand", ("", "same", "opposite")), ("remove_if_overlap", cls.REMOVE_MODES)):
            validation = cls.validate_choice(inputs.get(key, ""), choices, key)
            if validation is not True:
                return validation
        return cls.validate_overlap_options(inputs)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "subtract", "-a", str(inputs["inputA"]), "-b", str(inputs["inputB"]))
        strand = cls.strand_flag(inputs.get("strand"))
        if strand:
            command.append(strand)
        cls.add_overlap_options(command, inputs)
        mode = str(inputs.get("remove_if_overlap", ""))
        if mode:
            command.append("-A" if mode == "remove_feature" else "-N")
        return command
