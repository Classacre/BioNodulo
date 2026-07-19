"""RSeQC ``inner_distance.py`` node pinned to the 5.0.3 sdist."""

from __future__ import annotations

from typing import Any

from .adapter import RSeQCCommandNode


class RSeQCInnerDistanceNode(RSeQCCommandNode):
    """Calculate paired-read mRNA inner distances and the RSeQC histogram."""

    NODE_ID = "rseqc_inner_distance"
    DISPLAY_NAME = "RSeQC Inner Distance"
    DESCRIPTION = "Calculate mRNA inner distances for paired RNA-seq reads against a BED gene model."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "RSeQC",
        "inner_distance.py",
        "inner distance",
        "insert size",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TEXT", "IMAGE")
    RETURN_NAMES = (
        "inner_distances",
        "inner_distance_frequency",
        "r_script",
        "inner_distance_plot",
    )
    REQUIRED_EXECUTABLES = ["inner_distance.py", "Rscript"]
    REQUIRED_CONDA_PACKAGES = ["rseqc", "r-base"]
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#inner-distance-py"
    UPSTREAM_SCRIPT = "scripts/inner_distance.py"
    UPSTREAM_SOURCE = UPSTREAM_SCRIPT
    UPSTREAM_OUTPUT_SOURCE = "lib/qcmodule/SAM.py:mRNA_inner_distance"
    OUTPUT_FILENAMES = (
        "output.inner_distance.txt",
        "output.inner_distance_freq.txt",
        "output.inner_distance_plot.r",
        "output.inner_distance_plot.pdf",
    )
    REQUIRED_PATH_INPUTS = ("input", "refgene")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    ("BAM", "SAM"),
                    {"description": "BAM or SAM paired-end alignment file"},
                ),
                "refgene": (
                    "BED",
                    {"description": "Reference gene model in BED format"},
                ),
            },
            "optional": {
                "sample_size": (
                    "INT",
                    {
                        "default": 1000000,
                        "min": 1,
                        "description": "Number of read pairs used to estimate inner distance",
                    },
                ),
                "lower_bound": (
                    "INT",
                    {"default": -250, "description": "Lower plotting bound in bp"},
                ),
                "upper_bound": (
                    "INT",
                    {"default": 250, "description": "Upper plotting bound in bp"},
                ),
                "step": (
                    "INT",
                    {"default": 5, "min": 1, "description": "Histogram step in bp"},
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
        for key, default, minimum, maximum in (
            ("sample_size", 1000000, 1, None),
            ("step", 5, 1, None),
            ("mapq", 30, 0, 255),
        ):
            validation = cls.validate_int(inputs.get(key, default), key, minimum=minimum, maximum=maximum)
            if validation is not True:
                return validation
        for key, default in (("lower_bound", -250), ("upper_bound", 250)):
            validation = cls.validate_int(inputs.get(key, default), key)
            if validation is not True:
                return validation
        if inputs.get("lower_bound", -250) >= inputs.get("upper_bound", 250):
            return "lower_bound must be less than upper_bound"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "inner_distance.py")
        command.extend(
            [
                "-i",
                cls.path_value(inputs.get("input")),
                "-o",
                str(cls.output_prefix(inputs)),
                "-r",
                cls.path_value(inputs.get("refgene")),
                "-k",
                str(inputs.get("sample_size", 1000000)),
                "-l",
                str(inputs.get("lower_bound", -250)),
                "-u",
                str(inputs.get("upper_bound", 250)),
                "-s",
                str(inputs.get("step", 5)),
                "-q",
                str(inputs.get("mapq", 30)),
            ]
        )
        return command
