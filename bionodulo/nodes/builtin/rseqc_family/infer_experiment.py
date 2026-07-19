"""RSeQC 5.0.3 ``infer_experiment.py`` node."""

from __future__ import annotations

from typing import Any

from .adapter import RSeQCCommandNode


class RSeQCInferExperimentNode(RSeQCCommandNode):
    """Infer RNA-seq library layout and strandedness from an alignment file."""

    NODE_ID = "rseqc_infer_experiment"
    DISPLAY_NAME = "RSeQC Infer Experiment"
    DESCRIPTION = "Infer RNA-seq library layout and strandedness from SAM/BAM alignments."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "RSeQC",
        "infer_experiment",
        "strandedness",
        "library orientation",
    ]
    RETURN_TYPES = ("STATS_FILE",)
    RETURN_NAMES = ("infer_experiment",)
    REQUIRED_EXECUTABLES = ["infer_experiment.py"]
    OUTPUT_FILENAMES = ("infer_experiment.txt",)
    STDOUT_OUTPUT_INDEX = 0
    UPSTREAM_SCRIPT = "scripts/infer_experiment.py"
    UPSTREAM_SOURCE = UPSTREAM_SCRIPT
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#infer-experiment-py"

    REQUIRED_PATH_INPUTS = ("input", "refgene")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (("BAM", "SAM"), {"description": "SAM or BAM alignment file"}),
                "refgene": ("BED", {"description": "Reference gene model in BED format"}),
            },
            "optional": {
                "sample_size": (
                    "INT",
                    {"default": 200000, "min": 1, "description": "Number of reads sampled"},
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
        validation = cls.validate_int(inputs.get("sample_size", 200000), "sample_size", minimum=1)
        if validation is not True:
            return validation
        validation = cls.validate_int(inputs.get("mapq", 30), "mapq", minimum=0, maximum=255)
        if validation is not True:
            return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(
            inputs, "infer_experiment.py", "-i", str(inputs["input"]), "-r", str(inputs["refgene"])
        )
        command.extend(["-s", str(inputs.get("sample_size", 200000)), "-q", str(inputs.get("mapq", 30))])
        return command
