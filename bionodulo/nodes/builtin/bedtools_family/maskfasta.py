"""BEDTools maskfasta node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsCommandNode


class BEDToolsMaskFastaNode(BEDToolsCommandNode):
    NODE_ID = "bedtools_maskfastabed"
    DISPLAY_NAME = "BEDTools Mask FASTA"
    DESCRIPTION = "Mask reference sequence bases overlapping BED intervals"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "maskfasta", "maskfastabed", "soft mask"]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("masked_fasta",)
    OUTPUT_FILENAMES = ("masked.fasta",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/maskfasta.html"
    UPSTREAM_SOURCE = "src/maskFastaFromBed/maskFastaFromBed.cpp"
    REQUIRED_PATH_INPUTS = ("input", "fasta")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input": ("BED", {}), "fasta": ("FASTA", {})},
            "optional": {
                "soft": ("BOOLEAN", {"default": False}),
                "mask_character": ("STRING", {"default": "N"}),
                "full_header": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if "mc" in inputs or "fullheader" in inputs:
            return "legacy mc/fullheader inputs are stale; use mask_character/full_header"
        character = str(inputs.get("mask_character", "N"))
        if len(character) != 1:
            return "mask_character must be exactly one character"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "maskfasta")
        if inputs.get("soft"):
            command.append("-soft")
        else:
            command.extend(["-mc", str(inputs.get("mask_character", "N"))])
        command.extend([
            "-fi", str(inputs["fasta"]), "-bed", str(inputs["input"]),
            "-fo", str(cls.output_dir(inputs) / "masked.fasta"),
        ])
        if inputs.get("full_header"):
            command.append("-fullHeader")
        return command
