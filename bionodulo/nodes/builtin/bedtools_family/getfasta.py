"""BEDTools getfasta node pinned to 2.31.1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import BEDToolsCommandNode


class BEDToolsGetFastaNode(BEDToolsCommandNode):
    NODE_ID = "bedtools_getfastabed"
    DISPLAY_NAME = "BEDTools getfasta"
    DESCRIPTION = "Extract reference sequence for genomic intervals"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "getfasta", "getfastabed", "extract sequence"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("extracted_sequences",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/getfasta.html"
    UPSTREAM_SOURCE = "src/fastaFromBed/fastaFromBed.cpp"
    REQUIRED_PATH_INPUTS = ("input", "fasta")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input": ("BED", {}), "fasta": ("FASTA", {})},
            "optional": {
                "name": ("BOOLEAN", {"default": False}),
                "name_only": ("BOOLEAN", {"default": False}),
                "tab": ("BOOLEAN", {"default": False}),
                "strand": ("BOOLEAN", {"default": False}),
                "split": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if "nameOnly" in inputs:
            return "nameOnly is stale; use name_only"
        if inputs.get("name") and inputs.get("name_only"):
            return "name and name_only are mutually exclusive"
        return True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / ("extracted.tsv" if inputs.get("tab") else "extracted.fasta")]

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        cls.stage_writable_fasta(inputs, outputs)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "bedtools", "getfasta")
        if inputs.get("name"):
            command.append("-name")
        elif inputs.get("name_only"):
            command.append("-nameOnly")
        if inputs.get("tab"):
            command.append("-tab")
        if inputs.get("strand"):
            command.append("-s")
        if inputs.get("split"):
            command.append("-split")
        output = cls.output_dir(inputs) / ("extracted.tsv" if inputs.get("tab") else "extracted.fasta")
        command.extend(["-fi", str(inputs["fasta"]), "-bed", str(inputs["input"]), "-fo", str(output)])
        return command
