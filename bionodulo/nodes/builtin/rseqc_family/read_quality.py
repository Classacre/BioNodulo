"""RSeQC ``read_quality.py`` node pinned to the 5.0.3 sdist."""

from __future__ import annotations

from typing import Any

from .adapter import RSeQCCommandNode


class RSeQCReadQualityNode(RSeQCCommandNode):
    """Calculate per-base Phred quality plots for an alignment file."""

    NODE_ID = "rseqc_read_quality"
    DISPLAY_NAME = "RSeQC Read Quality"
    DESCRIPTION = "Calculate Phred quality distributions and plots for BAM or SAM alignments."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "RSeQC",
        "read_quality.py",
        "read quality",
        "Phred quality",
    ]
    RETURN_TYPES = ("TEXT", "IMAGE", "IMAGE")
    RETURN_NAMES = ("r_script", "quality_boxplot", "quality_heatmap")
    REQUIRED_EXECUTABLES = ["read_quality.py", "Rscript"]
    REQUIRED_CONDA_PACKAGES = ["rseqc", "r-base"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#read-quality-py"
    UPSTREAM_SCRIPT = "scripts/read_quality.py"
    UPSTREAM_SOURCE = UPSTREAM_SCRIPT
    UPSTREAM_SCRIPT_VERSION = "2.6.2"
    UPSTREAM_OUTPUT_SOURCE = "lib/qcmodule/SAM.py:readsQual_boxplot"
    OUTPUT_FILENAMES = (
        "output.qual.r",
        "output.qual.boxplot.pdf",
        "output.qual.heatmap.pdf",
    )
    REQUIRED_PATH_INPUTS = ("input",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    ("BAM", "SAM"),
                    {"description": "BAM or SAM alignment file"},
                ),
            },
            "optional": {
                "reduce": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "description": "Minimum count retained in the boxplot quality vectors",
                    },
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
        validation = cls.validate_int(inputs.get("reduce", 1), "reduce", minimum=1)
        if validation is not True:
            return validation
        return cls.validate_int(inputs.get("mapq", 30), "mapq", minimum=0, maximum=255)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "read_quality.py")
        command.extend(
            [
                "-i",
                cls.path_value(inputs.get("input")),
                "-o",
                str(cls.output_prefix(inputs)),
                "-r",
                str(inputs.get("reduce", 1)),
                "-q",
                str(inputs.get("mapq", 30)),
            ]
        )
        return command
