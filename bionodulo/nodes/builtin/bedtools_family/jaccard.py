"""BEDTools jaccard node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsJaccardNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_jaccard"
    DISPLAY_NAME = "BEDTools Jaccard"
    DESCRIPTION = "Calculate Jaccard similarity for two sorted interval sets"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "jaccard", "jaccardbed", "interval similarity"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("jaccard",)
    OUTPUT_FILENAMES = ("jaccard.tsv",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/jaccard.html"
    UPSTREAM_SOURCE = "src/jaccard/jaccard.cpp"
    REQUIRED_PATH_INPUTS = ("inputA", "inputB")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"inputA": ("BED", {}), "inputB": ("BED", {})},
            "optional": {
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1}),
                "overlap_b": ("FLOAT", {"default": "", "min": 0, "max": 1}),
                "reciprocal": ("BOOLEAN", {"default": False}),
                "either_fraction": ("BOOLEAN", {"default": False}),
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "split": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = cls.validate_choice(inputs.get("strand", ""), ("", "same", "opposite"), "strand")
        if validation is not True:
            return validation
        return cls.validate_overlap_options(inputs)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "jaccard", "-a", str(inputs["inputA"]), "-b", str(inputs["inputB"]))
        strand = cls.strand_flag(inputs.get("strand"))
        if strand:
            command.append(strand)
        if inputs.get("split"):
            command.append("-split")
        cls.add_overlap_options(command, inputs)
        return command
