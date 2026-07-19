"""RSeQC mismatch-profile node pinned to the 5.0.3 sdist."""

from __future__ import annotations

from typing import Any

from .adapter import RSeQCCommandNode


class RSeQCMismatchProfileNode(RSeQCCommandNode):
    """Calculate mismatch frequency by aligned read position."""

    NODE_ID = "rseqc_mismatch_profile"
    DISPLAY_NAME = "RSeQC Mismatch Profile"
    DESCRIPTION = "Calculate the distribution of mismatches across read positions."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "RSeQC",
        "mismatch_profile.py",
        "mismatch profile",
        "MD tag",
        "RNA-seq QC",
    ]
    RETURN_TYPES = ("TSV", "TEXT", "IMAGE")
    RETURN_NAMES = ("mismatch_profile", "r_script", "mismatch_profile_plot")
    OUTPUT_FILENAMES = (
        "output.mismatch_profile.xls",
        "output.mismatch_profile.r",
        "output.mismatch_profile.pdf",
    )
    REQUIRED_PATH_INPUTS = ("input",)
    REQUIRED_EXECUTABLES = ["mismatch_profile.py", "Rscript"]
    REQUIRED_CONDA_PACKAGES = ["rseqc", "r-base"]
    UPSTREAM_SCRIPT = "scripts/mismatch_profile.py"
    UPSTREAM_SOURCE = "scripts/mismatch_profile.py"
    UPSTREAM_OUTPUT_SOURCE = "lib/qcmodule/SAM.py:mismatchProfile"
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#mismatch-profile-py"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    "BAM",
                    {"description": "Input BAM alignment file containing MD tags"},
                ),
                "read_align_length": (
                    "INT",
                    {
                        "min": 1,
                        "description": "Original aligned read length (for example, 101 for a 101M read)",
                    },
                ),
            },
            "optional": {
                "read_num": (
                    "INT",
                    {
                        "default": 1000000,
                        "min": 1,
                        "description": "Number of aligned reads with mismatches to sample",
                    },
                ),
                "mapq": (
                    "INT",
                    {"default": 30, "min": 0, "max": 255, "description": "Minimum mapping quality"},
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
            ("read_align_length", None, 1, None),
            ("read_num", 1000000, 1, None),
            ("mapq", 30, 0, 255),
        ):
            value = inputs.get(key, default)
            if value is None:
                continue
            validation = cls.validate_int(value, key, minimum=minimum, maximum=maximum)
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "mismatch_profile.py")
        command.extend(
            [
                "-i",
                cls.path_value(inputs["input"]),
                "-l",
                str(inputs["read_align_length"]),
                "-o",
                str(cls.output_prefix(inputs)),
                "-n",
                str(inputs.get("read_num", 1000000)),
                "-q",
                str(inputs.get("mapq", 30)),
            ]
        )
        return command
