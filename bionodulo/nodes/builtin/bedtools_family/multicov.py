"""BEDTools multicov node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsMultiCovNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_multicovtbed"
    DISPLAY_NAME = "BEDTools MultiCov"
    DESCRIPTION = "Count alignments from sorted indexed BAM files over intervals"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "multicov", "multicovbed", "bam counts"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("multicov",)
    OUTPUT_FILENAMES = ("multicov.bed",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/multicov.html"
    UPSTREAM_SOURCE = "src/multiBamCov/multiBamCov.cpp"
    REQUIRED_PATH_INPUTS = ("input",)
    REQUIRED_PATH_LIST_INPUTS = ("bams", "bam_indexes")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {}),
                "bams": ("BAM_LIST", {"description": "Coordinate-sorted BAM files"}),
                "bam_indexes": ("FILE_LIST", {"description": "Exact colocated <bam>.bai indexes"}),
            },
            "optional": {
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1}),
                "reciprocal": ("BOOLEAN", {"default": False}),
                "split": ("BOOLEAN", {"default": False}),
                "q": ("INT", {"default": 0, "min": 0, "max": 255}),
                "duplicate": ("BOOLEAN", {"default": False}),
                "failed": ("BOOLEAN", {"default": False}),
                "proper": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = cls.validate_colocated_bam_indexes(inputs)
        if validation is not True:
            return validation
        validation = cls.validate_choice(inputs.get("strand", ""), ("", "same", "opposite"), "strand")
        if validation is not True:
            return validation
        validation = cls.validate_fraction(inputs.get("overlap"), "overlap", allow_zero=False)
        if validation is not True:
            return validation
        if inputs.get("reciprocal") and inputs.get("overlap") in (None, ""):
            return "overlap is required for reciprocal mode"
        q = inputs.get("q", 0)
        validation = cls.validate_int(q, "q", minimum=0)
        if validation is not True:
            return validation
        return True if int(q) <= 255 else "Input 'q' must be at most 255"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "multicov", "-bed", str(inputs["input"]), "-bams")
        command.extend(cls.path_list(inputs["bams"]))
        strand = cls.strand_flag(inputs.get("strand"))
        if strand:
            command.append(strand)
        cls.optional_value(command, "-f", inputs.get("overlap"))
        if inputs.get("reciprocal"):
            command.append("-r")
        if inputs.get("split"):
            command.append("-split")
        command.extend(["-q", str(inputs.get("q", 0))])
        for key, flag in (("duplicate", "-D"), ("failed", "-F"), ("proper", "-p")):
            if inputs.get(key):
                command.append(flag)
        return command
