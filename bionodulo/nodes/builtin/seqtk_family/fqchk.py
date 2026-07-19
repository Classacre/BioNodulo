"""Seqtk 1.4 ``fqchk`` node."""

from __future__ import annotations

from typing import Any

from .adapter import SeqtkStdoutNode


class SeqTKFqchkNode(SeqtkStdoutNode):
    """Capture Seqtk's native FASTQ base/quality summary."""

    NODE_ID = "seqtk_fqchk"
    DISPLAY_NAME = "SeqTK FASTQ Check"
    CATEGORY = "qc"
    DESCRIPTION = "Report per-cycle base composition and FASTQ quality statistics."
    SEARCH_ALIASES = ["BioNodulo builtin", "Seqtk", "fqchk", "FASTQ quality", "per-cycle QC"]
    RETURN_TYPES = ("STATS_FILE",)
    RETURN_NAMES = ("quality_information",)
    OUTPUT_FILENAMES = ("quality_information.txt",)
    REQUIRED_PATH_INPUTS = ("in_file",)
    UPSTREAM_FUNCTION = "stk_fqchk"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"in_file": ("FASTQ", {"description": "Input FASTQ, optionally gzip-compressed"})},
            "optional": {
                "q": ("INT", {"default": 20, "min": 0, "description": "Quality threshold; zero reports all values"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        return cls.validate_int(inputs.get("q", 20), "q", minimum=0)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return cls.checked_command(
            inputs,
            "seqtk",
            "fqchk",
            "-q",
            str(inputs.get("q", 20)),
            cls.path_value(inputs["in_file"]),
        )
