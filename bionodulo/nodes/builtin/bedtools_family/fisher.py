"""BEDTools fisher node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsFisherNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_fisher"
    DISPLAY_NAME = "BEDTools Fisher"
    DESCRIPTION = "Compute Fisher exact-test statistics for two sorted interval sets"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "fisher", "fisherbed", "overlap significance"]
    RETURN_TYPES = ("STATS_FILE",)
    RETURN_NAMES = ("fisher",)
    OUTPUT_FILENAMES = ("fisher.txt",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/fisher.html"
    UPSTREAM_SOURCE = "src/fisher/fisher.cpp"
    REQUIRED_PATH_INPUTS = ("inputA", "inputB", "genome")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"inputA": ("BED", {}), "inputB": ("BED", {}), "genome": ("TSV", {})},
            "optional": {
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "split": ("BOOLEAN", {"default": False}),
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1}),
                "overlap_b": ("FLOAT", {"default": "", "min": 0, "max": 1}),
                "reciprocal": ("BOOLEAN", {"default": False}),
                "either_fraction": ("BOOLEAN", {"default": False}),
                "merge": ("BOOLEAN", {"default": False}),
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
        command = cls.checked_command(inputs, "bedtools", "fisher", "-a", str(inputs["inputA"]), "-b", str(inputs["inputB"]), "-g", str(inputs["genome"]))
        strand = cls.strand_flag(inputs.get("strand"))
        if strand:
            command.append(strand)
        if inputs.get("split"):
            command.append("-split")
        cls.add_overlap_options(command, inputs)
        if inputs.get("merge"):
            command.append("-m")
        return command
