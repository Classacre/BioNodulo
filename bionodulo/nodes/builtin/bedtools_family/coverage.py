"""Compatibility BEDTools coverage ID pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsCoverageNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_coveragebed"
    COMPATIBILITY_ALIAS_OF = "bedtools_coverage"
    DISPLAY_NAME = "BEDTools Coverage"
    DESCRIPTION = "Report coverage of B records across A intervals"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "coverage", "coveragebed", "depth", "breadth"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("coverage",)
    OUTPUT_FILENAMES = ("coverage.tsv",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/coverage.html"
    UPSTREAM_SOURCE = "src/coverageFile/coverageFile.cpp"
    REQUIRED_PATH_INPUTS = ("inputA",)
    REQUIRED_PATH_LIST_INPUTS = ("inputB",)
    REPORTS = ("default", "d", "hist", "counts", "mean")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"inputA": ("FILE", {}), "inputB": ("FILE_LIST", {})},
            "optional": {
                "report": ("STRING", {"default": "default", "options": list(cls.REPORTS)}),
                "split": ("BOOLEAN", {"default": False}),
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "overlap_a": ("FLOAT", {"default": "", "min": 0, "max": 1}),
                "overlap_b": ("FLOAT", {"default": "", "min": 0, "max": 1}),
                "reciprocal_overlap": ("BOOLEAN", {"default": False}),
                "a_or_b": ("BOOLEAN", {"default": False}),
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
        stale = [key for key in ("d", "hist", "mean", "counts", "strandedness") if key in inputs]
        if stale:
            return f"Legacy coverage controls are stale ({', '.join(stale)}); use report and strand"
        for key in ("overlap_a", "overlap_b"):
            validation = cls.validate_fraction(inputs.get(key), key, allow_zero=False)
            if validation is not True:
                return validation
        if inputs.get("reciprocal_overlap") and inputs.get("overlap_a") in (None, ""):
            return "overlap_a is required for reciprocal overlap"
        if inputs.get("a_or_b") and inputs.get("overlap_a") in (None, ""):
            return "overlap_a is required for either-fraction overlap"
        if inputs.get("reciprocal_overlap") and inputs.get("a_or_b"):
            return "reciprocal and either-fraction overlap modes are mutually exclusive"
        if inputs.get("reciprocal_overlap") and inputs.get("overlap_b") not in (None, ""):
            return "overlap_b cannot be combined with reciprocal overlap"
        for key, choices, default in (("report", cls.REPORTS, "default"), ("strand", ("", "same", "opposite"), "")):
            validation = cls.validate_choice(inputs.get(key, default), choices, key)
            if validation is not True:
                return validation
        if inputs.get("genome") and not inputs.get("sorted"):
            return "genome is only valid with sorted=True"
        if str(inputs.get("inputA", "")).lower().endswith(".bam") and inputs.get("header"):
            return "header is ignored by BEDTools when inputA is BAM"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "coverage")
        report = str(inputs.get("report", "default"))
        if report != "default":
            command.append(f"-{report}")
        if inputs.get("split"):
            command.append("-split")
        strand = cls.strand_flag(inputs.get("strand"))
        if strand:
            command.append(strand)
        cls.optional_value(command, "-f", inputs.get("overlap_a"))
        cls.optional_value(command, "-F", inputs.get("overlap_b"))
        if inputs.get("reciprocal_overlap"):
            command.append("-r")
        elif inputs.get("a_or_b"):
            command.append("-e")
        command.extend(["-a", str(inputs["inputA"]), "-b", *cls.path_list(inputs["inputB"])])
        if inputs.get("sorted"):
            command.append("-sorted")
            cls.optional_value(command, "-g", inputs.get("genome"))
        if inputs.get("header"):
            command.append("-header")
        return command
