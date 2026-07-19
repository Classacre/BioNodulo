"""RSeQC ``junction_annotation.py`` node pinned to the 5.0.3 sdist."""

from __future__ import annotations

from typing import Any

from .adapter import RSeQCCommandNode


class RSeQCJunctionAnnotationNode(RSeQCCommandNode):
    """Annotate observed splice junctions against a BED12 gene model."""

    NODE_ID = "rseqc_junction_annotation"
    DISPLAY_NAME = "RSeQC Junction Annotation"
    DESCRIPTION = "Classify splice junctions as annotated or novel using a BED12 model."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "RSeQC",
        "junction_annotation.py",
        "junction annotation",
        "novel junctions",
    ]
    RETURN_TYPES = ("TSV", "TEXT", "IMAGE", "IMAGE", "BED", "BED")
    RETURN_NAMES = (
        "junctions",
        "r_script",
        "splice_events_plot",
        "splice_junction_plot",
        "junction_bed",
        "junction_interact_bed",
    )
    REQUIRED_EXECUTABLES = ["junction_annotation.py", "Rscript"]
    REQUIRED_CONDA_PACKAGES = ["rseqc", "r-base"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#junction-annotation-py"
    UPSTREAM_SCRIPT = "scripts/junction_annotation.py"
    UPSTREAM_SOURCE = UPSTREAM_SCRIPT
    UPSTREAM_OUTPUT_SOURCE = (
        "lib/qcmodule/SAM.py:annotate_junction; scripts/junction_annotation.py:generate_bed12,generate_interact"
    )
    OUTPUT_FILENAMES = (
        "output.junction.xls",
        "output.junction_plot.r",
        "output.splice_events.pdf",
        "output.splice_junction.pdf",
        "output.junction.bed",
        "output.junction.Interact.bed",
    )
    REQUIRED_PATH_INPUTS = ("input", "refgene")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    ("BAM", "SAM"),
                    {"description": "BAM or SAM alignment file"},
                ),
                "refgene": (
                    "BED",
                    {"description": "Reference gene model in BED format"},
                ),
            },
            "optional": {
                "min_intron": (
                    "INT",
                    {"default": 50, "min": 1, "description": "Minimum intron length in bp"},
                ),
                "mapq": (
                    "INT",
                    {
                        "default": 30,
                        "min": 0,
                        "max": 255,
                        "description": "Minimum mapping quality",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if "rscript_output" in inputs:
            return "Legacy input 'rscript_output' is unsupported; the source always creates its R script"
        validation = cls.validate_int(inputs.get("min_intron", 50), "min_intron", minimum=1)
        if validation is not True:
            return validation
        return cls.validate_int(inputs.get("mapq", 30), "mapq", minimum=0, maximum=255)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "junction_annotation.py")
        command.extend(
            [
                "-i",
                cls.path_value(inputs.get("input")),
                "-r",
                cls.path_value(inputs.get("refgene")),
                "-o",
                str(cls.output_prefix(inputs)),
                "-m",
                str(inputs.get("min_intron", 50)),
                "-q",
                str(inputs.get("mapq", 30)),
            ]
        )
        return command
