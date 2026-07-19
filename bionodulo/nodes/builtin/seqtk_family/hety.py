"""Seqtk 1.4 ``hety`` node."""

from __future__ import annotations

from typing import Any

from .adapter import SeqtkStdoutNode


class SeqTKHetyNode(SeqtkStdoutNode):
    """Report native sliding-window heterozygosity estimates."""

    NODE_ID = "seqtk_hety"
    DISPLAY_NAME = "SeqTK Heterozygosity"
    DESCRIPTION = "Report regional heterozygosity in sliding windows over FASTA/Q sequences."
    SEARCH_ALIASES = ["BioNodulo builtin", "Seqtk", "hety", "regional heterozygosity"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("heterozygous_regions",)
    OUTPUT_FILENAMES = ("heterozygous_regions.tsv",)
    REQUIRED_PATH_INPUTS = ("in_file",)
    UPSTREAM_FUNCTION = "stk_hety"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": (("FASTA", "FASTQ"), {"description": "Input FASTA/Q, optionally gzip-compressed"}),
            },
            "optional": {
                "w": ("INT", {"default": 50000, "min": 1, "description": "Window size"}),
                "t": ("INT", {"default": 5, "min": 1, "description": "Start positions per window"}),
                "m": ("BOOLEAN", {"default": False, "description": "Treat lowercase bases as masked"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        window = inputs.get("w", 50000)
        starts = inputs.get("t", 5)
        validation = cls.validate_int(window, "w", minimum=1)
        if validation is not True:
            return validation
        validation = cls.validate_int(starts, "t", minimum=1)
        if validation is not True:
            return validation
        # Seqtk uses w / t as a modulo step; t > w makes that step zero.
        if int(starts) > int(window):
            return "Input 't' must not exceed window size 'w'"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(
            inputs,
            "seqtk",
            "hety",
            "-w",
            str(inputs.get("w", 50000)),
            "-t",
            str(inputs.get("t", 5)),
        )
        if inputs.get("m"):
            command.append("-m")
        command.append(cls.path_value(inputs["in_file"]))
        return command
