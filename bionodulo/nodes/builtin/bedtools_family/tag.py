"""BEDTools tag node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsTagBedNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_tagbed"
    DISPLAY_NAME = "BEDTools TagBed"
    DESCRIPTION = "Populate a BAM tag from overlapping annotation files"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "tag", "tagbed", "BAM tags"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("tagged_bam",)
    OUTPUT_FILENAMES = ("tagged.bam",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/tag.html"
    UPSTREAM_SOURCE = "src/tagBam/tagBam.cpp"
    REQUIRED_PATH_INPUTS = ("inputA",)
    REQUIRED_PATH_LIST_INPUTS = ("inputB",)
    FIELDS = ("labels", "names", "scores")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"inputA": ("BAM", {}), "inputB": ("FILE_LIST", {})},
            "optional": {
                "labels": ("STRING_LIST", {}),
                "field": ("STRING", {"default": "labels", "options": list(cls.FIELDS)}),
                "intervals": ("BOOLEAN", {"default": False}),
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1}),
                "tag": ("STRING", {"default": "YB"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        field = str(inputs.get("field", "labels"))
        if field not in cls.FIELDS:
            return f"Unsupported tag field mode: {field}"
        validation = cls.validate_choice(inputs.get("strand", ""), ("", "same", "opposite"), "strand")
        if validation is not True:
            return validation
        validation = cls.validate_fraction(inputs.get("overlap"), "overlap", allow_zero=False)
        if validation is not True:
            return validation
        tag = str(inputs.get("tag", "YB"))
        if not 1 <= len(tag) <= 2:
            return "tag must contain one or two characters"
        labels = [str(label) for label in inputs.get("labels", [])]
        files = cls.path_list(inputs.get("inputB"))
        if field == "labels" or inputs.get("intervals"):
            if len(labels) != len(files):
                return "labels must contain exactly one value per annotation file"
        elif labels:
            return "labels are only valid in labels mode or with intervals=True"
        if inputs.get("intervals") and field != "labels":
            return "intervals requires field=labels"
        if str(inputs.get("field", "")).startswith("-"):
            return "legacy raw field flags are stale; use labels, names, or scores"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "tag", "-i", str(inputs["inputA"]), "-files")
        command.extend(cls.path_list(inputs["inputB"]))
        field = str(inputs.get("field", "labels"))
        if field == "labels":
            command.extend(["-labels", *[str(label) for label in inputs.get("labels", [])]])
            if inputs.get("intervals"):
                command.append("-intervals")
        else:
            command.append(f"-{field}")
        strand = cls.strand_flag(inputs.get("strand"))
        if strand:
            command.append(strand)
        cls.optional_value(command, "-f", inputs.get("overlap"))
        command.extend(["-tag", str(inputs.get("tag", "YB"))])
        return command
