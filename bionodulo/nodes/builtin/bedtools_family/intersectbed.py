"""Compatibility BEDTools intersect ID pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsIntersectBedNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_intersectbed"
    COMPATIBILITY_ALIAS_OF = "bedtools_intersect"
    DISPLAY_NAME = "BEDTools Intersect Intervals"
    DESCRIPTION = "Report overlaps between one A file and one or more B files"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "intersect", "intersectbed", "overlap intervals"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("intersect",)
    OUTPUT_FILENAMES = ("intersect.out",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/intersect.html"
    UPSTREAM_SOURCE = "src/intersectFile/intersectFile.cpp"
    REQUIRED_PATH_INPUTS = ("inputA",)
    REQUIRED_PATH_LIST_INPUTS = ("inputB",)
    REPORTS = ("default", "wa", "wb", "wo", "wao", "loj", "u", "v", "c", "C")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"inputA": ("FILE", {}), "inputB": ("FILE_LIST", {})},
            "optional": {
                "names": ("STRING_LIST", {}),
                "report": ("STRING", {"default": "default", "options": list(cls.REPORTS)}),
                "split": ("BOOLEAN", {"default": False}),
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1}),
                "overlap_b": ("FLOAT", {"default": "", "min": 0, "max": 1}),
                "reciprocal": ("BOOLEAN", {"default": False}),
                "either_fraction": ("BOOLEAN", {"default": False}),
                "bed": ("BOOLEAN", {"default": False}),
                "sorted": ("BOOLEAN", {"default": False}),
                "genome": ("TSV", {"default": ""}),
                "header": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        stale = [key for key in ("overlap_mode", "invert", "once", "count", "overlapB", "disjoint") if key in inputs]
        if stale:
            return f"Legacy intersect controls are stale ({', '.join(stale)}); use report and canonical overlap inputs"
        report = str(inputs.get("report", "default"))
        if report not in cls.REPORTS:
            return f"Unsupported intersect report: {report}"
        validation = cls.validate_choice(inputs.get("strand", ""), ("", "same", "opposite"), "strand")
        if validation is not True:
            return validation
        validation = cls.validate_overlap_options(inputs)
        if validation is not True:
            return validation
        b_files = cls.path_list(inputs.get("inputB"))
        names = [str(name) for name in inputs.get("names", [])]
        if names and len(names) != len(b_files):
            return "Input 'names' must contain exactly one label per B file"
        if inputs.get("genome") and not inputs.get("sorted"):
            return "genome is only valid with sorted=True"
        is_bam = str(inputs.get("inputA", "")).lower().endswith(".bam")
        if inputs.get("bed") and not is_bam:
            return "bed output conversion is only valid when inputA is BAM"
        if is_bam and inputs.get("header"):
            return "header is ignored by BEDTools when inputA is BAM"
        if is_bam and report in ("wb", "wo", "wao", "loj", "c", "C") and not inputs.get("bed"):
            return f"report={report} requires bed=True when inputA is BAM"
        if report == "c" and names:
            return "report=c cannot be combined with names; use report=C"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "intersect", "-a", str(inputs["inputA"]), "-b")
        command.extend(cls.path_list(inputs["inputB"]))
        names = [str(name) for name in inputs.get("names", [])]
        if names:
            command.extend(["-names", *names])
        report = str(inputs.get("report", "default"))
        if report != "default":
            command.append(f"-{report}")
        if inputs.get("split"):
            command.append("-split")
        strand = cls.strand_flag(inputs.get("strand"))
        if strand:
            command.append(strand)
        cls.add_overlap_options(command, inputs)
        if inputs.get("sorted"):
            command.append("-sorted")
            cls.optional_value(command, "-g", inputs.get("genome"))
        if inputs.get("header"):
            command.append("-header")
        if inputs.get("bed"):
            command.append("-bed")
        return command
