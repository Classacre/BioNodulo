"""BEDTools annotate node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsAnnotateNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_annotatebed"
    DISPLAY_NAME = "BEDTools Annotate"
    DESCRIPTION = "Annotate intervals with coverage or counts from multiple feature files"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "annotate", "annotatebed", "coverage annotation"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("annotated",)
    OUTPUT_FILENAMES = ("annotated.bed",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/annotate.html"
    UPSTREAM_SOURCE = "src/annotateBed/annotateMain.cpp"
    REQUIRED_PATH_INPUTS = ("inputA",)
    REQUIRED_PATH_LIST_INPUTS = ("beds",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"inputA": ("BED", {}), "beds": ("BED_LIST", {})},
            "optional": {
                "names": ("STRING_LIST", {}),
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "counts": ("BOOLEAN", {"default": False}),
                "both": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        beds = cls.path_list(inputs.get("beds"))
        names = [str(name) for name in inputs.get("names", [])]
        if names and len(names) != len(beds):
            return "Input 'names' must contain exactly one label per annotation file"
        if inputs.get("counts") and inputs.get("both"):
            return "counts and both report modes are mutually exclusive"
        return cls.validate_choice(inputs.get("strand", ""), ("", "same", "opposite"), "strand")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "annotate", "-i", str(inputs["inputA"]), "-files")
        command.extend(cls.path_list(inputs["beds"]))
        names = [str(name) for name in inputs.get("names", [])]
        if names:
            command.extend(["-names", *names])
        strand = cls.strand_flag(inputs.get("strand"))
        if strand:
            command.append(strand)
        if inputs.get("counts"):
            command.append("-counts")
        elif inputs.get("both"):
            command.append("-both")
        return command
