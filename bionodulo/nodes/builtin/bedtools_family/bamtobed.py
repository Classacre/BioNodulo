"""BEDTools bamtobed node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsBamToBedNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_bamtobed"
    DISPLAY_NAME = "BEDTools BAM to BED"
    DESCRIPTION = "Convert BAM alignments to BED6, BED12, or BEDPE"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "bamtobed", "bam to bed", "bed12", "bedpe"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("converted_bed",)
    OUTPUT_FILENAMES = ("converted.bed",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/bamtobed.html"
    UPSTREAM_SOURCE = "src/bamToBed/bamToBed.cpp"
    REQUIRED_PATH_INPUTS = ("input",)
    MODES = ("", "bed12", "bedpe")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM input; BEDPE mode requires query-name grouping"}),
                "option": ("STRING", {"default": "", "options": list(cls.MODES)}),
            },
            "optional": {
                "split": ("BOOLEAN", {"default": False}),
                "ed_score": ("BOOLEAN", {"default": False}),
                "tag": ("STRING", {"default": ""}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        mode = str(inputs.get("option", ""))
        if mode not in cls.MODES:
            return f"Unsupported bamtobed output mode: {mode}"
        if inputs.get("ed_score") and str(inputs.get("tag", "")).strip():
            return "ed_score and tag score modes are mutually exclusive"
        if inputs.get("ed_score") and (inputs.get("split") or mode == "bed12"):
            return "ed_score is incompatible with split or BED12 output"
        if mode == "bedpe" and str(inputs.get("tag", "")).strip():
            return "tag score mode is not supported with BEDPE output"
        if mode == "bedpe" and inputs.get("split"):
            return "split is ignored by BEDTools with BEDPE output"
        if "threads" in inputs:
            return "threads is stale; bamtobed does not sort BAM input"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "bamtobed")
        mode = str(inputs.get("option", ""))
        if mode:
            command.append(f"-{mode}")
        if inputs.get("split"):
            command.append("-split")
        if inputs.get("ed_score"):
            command.append("-ed")
        elif str(inputs.get("tag", "")).strip():
            command.extend(["-tag", str(inputs["tag"])])
        command.extend(["-i", str(inputs["input"])])
        return command
