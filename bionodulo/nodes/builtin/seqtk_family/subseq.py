"""Seqtk 1.4 ``subseq`` node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqtkStdoutNode


class SeqTKSubseqNode(SeqtkStdoutNode):
    """Extract records or intervals named by a BED/name-list file."""

    NODE_ID = "seqtk_subseq"
    DISPLAY_NAME = "SeqTK Subsequence"
    DESCRIPTION = "Extract FASTA/Q records or intervals from a BED or sequence-name list."
    SEARCH_ALIASES = ["BioNodulo builtin", "Seqtk", "subseq", "extract sequences", "BED regions"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("selected_records",)
    REQUIRED_PATH_INPUTS = ("in_file", "regions")
    UPSTREAM_FUNCTION = "stk_subseq"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": (("FASTA", "FASTQ"), {"description": "Input FASTA/Q, optionally gzip-compressed"}),
                "regions": ("FILE", {"description": "BED intervals or newline-delimited sequence names"}),
            },
            "optional": {
                "t": ("BOOLEAN", {"default": False, "description": "Emit native tab-delimited output"}),
                "l": ("INT", {"default": 0, "min": 0, "description": "Sequence line length"}),
                "s": ("BOOLEAN", {"default": False, "description": "Honor BED strand; source supports FASTA only"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        extension = ".tsv" if inputs.get("t") else cls.sequence_extension(inputs.get("in_file"))
        return [node_dir / f"selected{extension}"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = cls.reject_legacy(
            inputs,
            ("input_ext", "source_type", "in_bed", "name_list"),
        )
        if validation is not True:
            return validation
        return cls.validate_int(inputs.get("l", 0), "l", minimum=0)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "seqtk", "subseq")
        if inputs.get("t"):
            command.append("-t")
        command.extend(["-l", str(inputs.get("l", 0))])
        if inputs.get("s"):
            command.append("-s")
        command.extend([cls.path_value(inputs["in_file"]), cls.path_value(inputs["regions"])])
        return command
