"""RSeQC read-duplication node pinned to the 5.0.3 sdist."""

from __future__ import annotations

from typing import Any

from .adapter import RSeQCCommandNode


class RSeQCReadDuplicationNode(RSeQCCommandNode):
    """Estimate sequence- and position-based read duplication rates."""

    NODE_ID = "rseqc_read_duplication"
    DISPLAY_NAME = "RSeQC Read Duplication"
    DESCRIPTION = "Determine read duplication rates from mapping positions and read sequences."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "RSeQC",
        "read_duplication.py",
        "read duplication",
        "duplication rate",
        "PCR bias",
        "RNA-seq QC",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TEXT", "IMAGE")
    RETURN_NAMES = ("sequence_duplication", "position_duplication", "r_script", "duplication_plot")
    OUTPUT_FILENAMES = (
        "output.seq.DupRate.xls",
        "output.pos.DupRate.xls",
        "output.DupRate_plot.r",
        "output.DupRate_plot.pdf",
    )
    REQUIRED_PATH_INPUTS = ("input",)
    REQUIRED_EXECUTABLES = ["read_duplication.py", "Rscript"]
    REQUIRED_CONDA_PACKAGES = ["rseqc", "r-base"]
    UPSTREAM_SCRIPT = "scripts/read_duplication.py"
    UPSTREAM_SOURCE = "scripts/read_duplication.py"
    UPSTREAM_OUTPUT_SOURCE = "lib/qcmodule/SAM.py:readDupRate"
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#read-duplication-py"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    ("BAM", "SAM"),
                    {"description": "Input BAM or SAM alignment file"},
                ),
            },
            "optional": {
                "up_limit": (
                    "INT",
                    {
                        "default": 500,
                        "min": 1,
                        "description": "Upper occurrence limit used for duplication plots",
                    },
                ),
                "mapq": (
                    "INT",
                    {
                        "default": 30,
                        "min": 0,
                        "max": 255,
                        "description": "Minimum mapping quality for uniquely mapped reads",
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
        validation = cls.validate_int(inputs.get("up_limit", 500), "up_limit", minimum=1)
        if validation is not True:
            return validation
        return cls.validate_int(inputs.get("mapq", 30), "mapq", minimum=0, maximum=255)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "read_duplication.py")
        command.extend(
            [
                "-i",
                cls.path_value(inputs["input"]),
                "-o",
                str(cls.output_prefix(inputs)),
                "-u",
                str(inputs.get("up_limit", 500)),
                "-q",
                str(inputs.get("mapq", 30)),
            ]
        )
        return command
