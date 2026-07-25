"""BEDTools nuc node pinned to 2.31.1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsNucNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_nucbed"
    DISPLAY_NAME = "BEDTools Nucleotide Content"
    DESCRIPTION = "Report nucleotide composition and optional motif counts for intervals"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "nuc", "nucbed", "gc content"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("nucleotide_content",)
    OUTPUT_FILENAMES = ("nucleotide_content.tsv",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/nuc.html"
    UPSTREAM_SOURCE = "src/nucBed/nucBed.cpp"
    REQUIRED_PATH_INPUTS = ("input", "fasta")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input": ("BED", {}), "fasta": ("FASTA", {})},
            "optional": {
                "strand": ("BOOLEAN", {"default": False}),
                "seq": ("BOOLEAN", {"default": False}),
                "pattern": ("STRING", {"default": ""}),
                "ignore_case": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if inputs.get("ignore_case") and not str(inputs.get("pattern", "")).strip():
            return "ignore_case requires a non-empty pattern"
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        cls.stage_writable_fasta(inputs, outputs)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "nuc")
        if inputs.get("strand"):
            command.append("-s")
        if inputs.get("seq"):
            command.append("-seq")
        pattern = str(inputs.get("pattern", "")).strip()
        if pattern:
            command.extend(["-pattern", pattern])
            if inputs.get("ignore_case"):
                command.append("-C")
        command.extend(["-fi", str(inputs["fasta"]), "-bed", str(inputs["input"])])
        return command
