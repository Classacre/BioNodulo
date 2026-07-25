"""Seqtk 1.4 ``mergefa`` node."""

from __future__ import annotations

from typing import Any

from .adapter import SeqtkStdoutNode


class SeqTKMergeFANode(SeqtkStdoutNode):
    """Merge two aligned FASTA/Q streams into IUPAC FASTA."""

    NODE_ID = "seqtk_mergefa"
    DISPLAY_NAME = "SeqTK Merge FASTA"
    DESCRIPTION = "Merge paired records base-by-base into FASTA and report native merge counts."
    SEARCH_ALIASES = ["BioNodulo builtin", "Seqtk", "mergefa", "IUPAC merge"]
    RETURN_TYPES = ("FASTA", "STATS_FILE")
    RETURN_NAMES = ("merged_fasta", "merge_stats")
    OUTPUT_FILENAMES = ("merged.fasta", "mergefa.stats.txt")
    STDERR_OUTPUT_INDEX = 1
    REQUIRED_PATH_INPUTS = ("in_fa1", "in_fa2")
    UPSTREAM_FUNCTION = "stk_mergefa"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_fa1": (("FASTA", "FASTQ"), {"description": "First aligned FASTA/Q input"}),
                "in_fa2": (("FASTA", "FASTQ"), {"description": "Second aligned FASTA/Q input"}),
            },
            "optional": {
                "q": ("INT", {"default": 0, "min": 0, "description": "FASTQ quality threshold"}),
                "i": ("BOOLEAN", {"default": False, "description": "Take the base intersection"}),
                "m": ("BOOLEAN", {"default": False, "description": "Mask when either input base is N"}),
                "r": ("BOOLEAN", {"default": False, "description": "Choose a random allele from heterozygotes"}),
                "h": ("BOOLEAN", {"default": False, "description": "Suppress heterozygous input bases"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = cls.reject_legacy(inputs, ("input_ext",))
        if validation is not True:
            return validation
        validation = cls.validate_int(inputs.get("q", 0), "q", minimum=0)
        if validation is not True:
            return validation
        if inputs.get("i") and inputs.get("m"):
            return "Seqtk mergefa options -i and -m are mutually exclusive"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "seqtk", "mergefa", "-q", str(inputs.get("q", 0)))
        for key, flag in (("i", "-i"), ("m", "-m"), ("r", "-r"), ("h", "-h")):
            if inputs.get(key):
                command.append(flag)
        command.extend([cls.path_value(inputs["in_fa1"]), cls.path_value(inputs["in_fa2"])])
        return command
