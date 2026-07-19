"""RSeQC 5.0.3 ``deletion_profile.py`` node."""

from __future__ import annotations

from typing import Any

from .adapter import RSeQCCommandNode


class RSeQCDeletionProfileNode(RSeQCCommandNode):
    """Calculate the distribution of deleted bases across aligned reads."""

    NODE_ID = "rseqc_deletion_profile"
    DISPLAY_NAME = "RSeQC Deletion Profile"
    DESCRIPTION = "Calculate the distribution of CIGAR deletions across aligned RNA-seq reads."
    SEARCH_ALIASES = ["BioNodulo builtin", "RSeQC", "deletion_profile", "deletions", "CIGAR"]
    RETURN_TYPES = ("TSV", "TEXT", "IMAGE")
    RETURN_NAMES = ("deletion_profile", "r_script", "deletion_plot")
    REQUIRED_EXECUTABLES = ["deletion_profile.py", "Rscript"]
    REQUIRED_CONDA_PACKAGES = ["rseqc", "r-base"]
    OUTPUT_FILENAMES = (
        "output.deletion_profile.txt",
        "output.deletion_profile.r",
        "output.deletion_profile.pdf",
    )
    UPSTREAM_SCRIPT = "scripts/deletion_profile.py"
    UPSTREAM_SOURCE = UPSTREAM_SCRIPT
    UPSTREAM_OUTPUT_SOURCE = "lib/qcmodule/SAM.py:deletionProfile"
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#deletion-profile-py"

    REQUIRED_PATH_INPUTS = ("input",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM alignment file"}),
                "read_align_length": (
                    "INT",
                    {"min": 1, "description": "Aligned read length, normally the original read length"},
                ),
            },
            "optional": {
                "read_num": ("INT", {"default": 1000000, "min": 1}),
                "mapq": ("INT", {"default": 30, "min": 0, "max": 255}),
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
        for key, value, minimum, maximum in (
            ("read_align_length", inputs.get("read_align_length"), 1, None),
            ("read_num", inputs.get("read_num", 1000000), 1, None),
            ("mapq", inputs.get("mapq", 30), 0, 255),
        ):
            validation = cls.validate_int(value, key, minimum=minimum, maximum=maximum)
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return cls.checked_command(
            inputs,
            "deletion_profile.py",
            "-i",
            str(inputs["input"]),
            "-l",
            str(inputs["read_align_length"]),
            "-o",
            str(cls.output_prefix(inputs, "output")),
            "-n",
            str(inputs.get("read_num", 1000000)),
            "-q",
            str(inputs.get("mapq", 30)),
        )
