"""BEDTools genomecov node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsGenomeCoverageNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_genomecoveragebed"
    DISPLAY_NAME = "BEDTools Genome Coverage"
    DESCRIPTION = "Compute a genome coverage report from sorted intervals or a coordinate-sorted BAM"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "genomecov", "genome coverage", "bedgraph"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("genome_coverage",)
    OUTPUT_FILENAMES = ("genome_coverage.tsv",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/genomecov.html"
    UPSTREAM_SOURCE = "src/genomeCoverageBed/genomeCoverageMain.cpp"
    REQUIRED_PATH_INPUTS = ("input",)
    REPORTS = ("bg", "bga", "hist", "d", "dz")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_type": ("STRING", {"default": "bed", "options": ["bed", "bam"]}),
                "input": ("FILE", {"description": "Sorted BED-like input or coordinate-sorted BAM"}),
                "report": ("STRING", {"default": "bg", "options": list(cls.REPORTS)}),
            },
            "optional": {
                "genome": ("TSV", {"default": ""}),
                "scale": ("FLOAT", {"default": 1.0, "min": 0}),
                "max": ("INT", {"default": "", "min": 0}),
                "split": ("BOOLEAN", {"default": False}),
                "strand": ("STRING", {"default": "", "options": ["", "+", "-"]}),
                "five": ("BOOLEAN", {"default": False}),
                "three": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        stale = [key for key in ("zero_regions", "d", "dz", "report_select", "input_type_select") if key in inputs]
        if stale:
            return f"Legacy genomecov controls are stale ({', '.join(stale)}); use report and input_type"
        input_type = str(inputs.get("input_type", "bed"))
        report = str(inputs.get("report", "bg"))
        if input_type not in ("bed", "bam"):
            return "input_type must be bed or bam"
        if report not in cls.REPORTS:
            return f"Unsupported genomecov report: {report}"
        if input_type == "bed":
            validation = cls.require_path(inputs, "genome")
            if validation is not True:
                return validation
        elif inputs.get("genome"):
            return "genome is not accepted with BAM input"
        if inputs.get("max") not in (None, "") and report != "hist":
            return "max is only valid for histogram output"
        if float(inputs.get("scale", 1.0)) != 1.0 and report not in ("bg", "bga", "d", "dz"):
            return "scale is only valid for bedGraph or per-base reports"
        if inputs.get("five") and inputs.get("three"):
            return "five and three end-only modes are mutually exclusive"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "genomecov")
        if inputs.get("input_type", "bed") == "bam":
            command.extend(["-ibam", str(inputs["input"])])
        else:
            command.extend(["-i", str(inputs["input"]), "-g", str(inputs["genome"])])
        report = str(inputs.get("report", "bg"))
        if report != "hist":
            command.append(f"-{report}")
        if inputs.get("split"):
            command.append("-split")
        if inputs.get("strand"):
            command.extend(["-strand", str(inputs["strand"])])
        if float(inputs.get("scale", 1.0)) != 1.0:
            command.extend(["-scale", str(inputs["scale"])])
        cls.optional_value(command, "-max", inputs.get("max"))
        if inputs.get("five"):
            command.append("-5")
        elif inputs.get("three"):
            command.append("-3")
        return command
