"""RSeQC read-distribution node pinned to the 5.0.3 sdist."""

from __future__ import annotations

from typing import Any

from .adapter import RSeQCCommandNode


class RSeQCReadDistributionNode(RSeQCCommandNode):
    """Capture the genomic-feature distribution report emitted on stdout."""

    NODE_ID = "rseqc_read_distribution"
    DISPLAY_NAME = "RSeQC Read Distribution"
    DESCRIPTION = "Calculate mapped-read distribution across a BED gene model."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "RSeQC",
        "read_distribution.py",
        "read distribution",
        "mapped reads",
        "genome features",
        "RNA-seq QC",
    ]
    RETURN_TYPES = ("STATS_FILE",)
    RETURN_NAMES = ("read_distribution",)
    OUTPUT_FILENAMES = ("read_distribution.txt",)
    STDOUT_OUTPUT_INDEX = 0
    REQUIRED_PATH_INPUTS = ("input", "refgene")
    REQUIRED_EXECUTABLES = ["read_distribution.py"]
    UPSTREAM_SCRIPT = "scripts/read_distribution.py"
    UPSTREAM_SOURCE = "scripts/read_distribution.py"
    UPSTREAM_OUTPUT_SOURCE = "scripts/read_distribution.py:main"
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#read-distribution-py"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    ("BAM", "SAM"),
                    {"description": "Input BAM or SAM alignment file"},
                ),
                "refgene": (
                    "BED",
                    {"description": "Reference gene model in BED12 format"},
                ),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "read_distribution.py")
        command.extend(
            [
                "-i",
                cls.path_value(inputs["input"]),
                "-r",
                cls.path_value(inputs["refgene"]),
            ]
        )
        return command
