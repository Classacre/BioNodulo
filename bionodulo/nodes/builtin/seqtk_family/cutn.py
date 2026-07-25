"""Seqtk 1.4 ``cutN`` node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqtkStdoutNode


class SeqTKCutNNode(SeqtkStdoutNode):
    """Split records at long N tracts or report those gaps as BED."""

    NODE_ID = "seqtk_cutN"
    DISPLAY_NAME = "SeqTK CutN"
    DESCRIPTION = "Split FASTA/Q records at long N tracts or report the gaps only."
    SEARCH_ALIASES = ["BioNodulo builtin", "Seqtk", "cutN", "N tracts", "assembly gaps"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("cut_sequences_or_gaps",)
    REQUIRED_PATH_INPUTS = ("in_file",)
    UPSTREAM_FUNCTION = "stk_cutN"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": (("FASTA", "FASTQ"), {"description": "Input FASTA/Q, optionally gzip-compressed"}),
            },
            "optional": {
                "n": ("INT", {"default": 1000, "min": 1, "description": "Minimum N-tract size"}),
                "p": ("INT", {"default": 10, "min": 0, "description": "Penalty for a non-N base"}),
                "g": ("BOOLEAN", {"default": False, "description": "Print gaps only as BED"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        filename = "gaps.bed" if inputs.get("g") else f"cutN{cls.sequence_extension(inputs.get('in_file'))}"
        return [node_dir / filename]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = cls.reject_legacy(inputs, ("input_ext",))
        if validation is not True:
            return validation
        validation = cls.validate_int(inputs.get("n", 1000), "n", minimum=1)
        if validation is not True:
            return validation
        return cls.validate_int(inputs.get("p", 10), "p", minimum=0)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(
            inputs,
            "seqtk",
            "cutN",
            "-n",
            str(inputs.get("n", 1000)),
            "-p",
            str(inputs.get("p", 10)),
        )
        if inputs.get("g"):
            command.append("-g")
        command.append(cls.path_value(inputs["in_file"]))
        return command
