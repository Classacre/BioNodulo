"""RSeQC BAM-stat node pinned to the 5.0.3 sdist."""

from __future__ import annotations

from typing import Any

from .adapter import RSeQCCommandNode


class RSeQCBamStatNode(RSeQCCommandNode):
    """Capture the mapping-statistics report emitted on stdout."""

    NODE_ID = "rseqc_bam_stat"
    DISPLAY_NAME = "RSeQC BAM Stat"
    DESCRIPTION = "Summarize mapping statistics for a BAM or SAM alignment."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "RSeQC",
        "bam_stat.py",
        "BAM statistics",
        "mapping statistics",
        "RNA-seq QC",
    ]
    RETURN_TYPES = ("STATS_FILE",)
    RETURN_NAMES = ("mapping_stats",)
    OUTPUT_FILENAMES = ("bam_stat.txt",)
    STDOUT_OUTPUT_INDEX = 0
    REQUIRED_PATH_INPUTS = ("input",)
    REQUIRED_EXECUTABLES = ["bam_stat.py"]
    UPSTREAM_SCRIPT = "scripts/bam_stat.py"
    UPSTREAM_SOURCE = "scripts/bam_stat.py"
    UPSTREAM_OUTPUT_SOURCE = "lib/qcmodule/SAM.py:stat"
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#bam-stat-py"

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
        return cls.validate_int(inputs.get("mapq", 30), "mapq", minimum=0, maximum=255)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bam_stat.py")
        command.extend(
            [
                "-i",
                cls.path_value(inputs["input"]),
                "-q",
                str(inputs.get("mapq", 30)),
            ]
        )
        return command
