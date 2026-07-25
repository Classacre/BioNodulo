"""Seqtk 1.4 ``telo`` node."""

from __future__ import annotations

from typing import Any

from .adapter import SeqtkStdoutNode


class SeqTKTeloNode(SeqtkStdoutNode):
    """Identify terminal telomere-repeat regions and capture aggregate counts."""

    NODE_ID = "seqtk_telo"
    DISPLAY_NAME = "SeqTK Telomere"
    DESCRIPTION = "Identify telomeric repeat regions and report telomeric versus total input bases."
    SEARCH_ALIASES = ["BioNodulo builtin", "Seqtk", "telo", "telomere", "CCCTAA"]
    RETURN_TYPES = ("BED", "STATS_FILE")
    RETURN_NAMES = ("telomeres", "telomere_counts")
    OUTPUT_FILENAMES = ("telomeres.bed", "telomere_counts.txt")
    STDERR_OUTPUT_INDEX = 1
    REQUIRED_PATH_INPUTS = ("in_file",)
    UPSTREAM_FUNCTION = "stk_telo"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": (("FASTA", "FASTQ"), {"description": "Input assembly or long reads"}),
            },
            "optional": {
                "m": ("STRING", {"default": "CCCTAA", "description": "Telomere motif"}),
                "p": ("INT", {"default": 1, "description": "Penalty for a non-repeat base"}),
                "d": ("INT", {"default": 2000, "min": 0, "description": "Maximum score drop"}),
                "s": ("INT", {"default": 300, "min": 0, "description": "Minimum telomere score"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = cls.reject_legacy(inputs, ("P",))
        if validation is not True:
            return validation
        motif = str(inputs.get("m", "CCCTAA"))
        # Seqtk packs the motif into 64 bits and asserts that every base is A/C/G/T.
        if not 1 <= len(motif) <= 31 or any(base not in "ACGTacgt" for base in motif):
            return "Input 'm' must contain 1 to 31 A/C/G/T bases"
        for key, default, minimum in (("p", 1, None), ("d", 2000, 0), ("s", 300, 0)):
            validation = cls.validate_int(inputs.get(key, default), key, minimum=minimum)
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return cls.checked_command(
            inputs,
            "seqtk",
            "telo",
            "-m",
            str(inputs.get("m", "CCCTAA")),
            "-p",
            str(inputs.get("p", 1)),
            "-d",
            str(inputs.get("d", 2000)),
            "-s",
            str(inputs.get("s", 300)),
            cls.path_value(inputs["in_file"]),
        )
