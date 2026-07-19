"""Focused biobox add taxid node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

class BioboxAddTaxidNode(CommandNode):
    """Add taxonomy IDs to CAMI AMBER biobox binning data."""

    NODE_ID = "biobox_add_taxid"
    DISPLAY_NAME = "Biobox add taxid"
    REQUIRED_CONDA_PACKAGES = ["biobox_add_taxid"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Add taxid output from BAT or GTDB to biobox binning data."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Biobox add taxid",
        "biobox_add_taxid.py",
        "CAMI AMBER biobox taxid",
        "ContigID2TaxID",
        "BinID2TaxID",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["biobox_add_taxid.py"]
    DOCUMENTATION_URL = "https://github.com/SantaMcCloud/biobox_add_taxid/tree/release-1.0"
    CITATION_URLS = ["https://github.com/SantaMcCloud/biobox_add_taxid/tree/release-1.0"]
    CITATION_TEXT = "biobox_add_taxid: add TaxID columns to CAMI AMBER biobox files."
    VERSION = "1.2+galaxy0"
    SHELL = True

    INPUT_MODES = ["contig", "bin"]

    @classmethod
    def _input_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_mode", inputs.get("is_select", "contig")) or "contig")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        mode = cls._input_mode(inputs)
        taxid_input = "contig2taxid" if mode == "contig" else "binid2taxid"
        staged_taxid = "contig.tsv" if mode == "contig" else "bin.tsv"
        taxid_flag = "-c" if mode == "contig" else "-b"
        commands = [
            _shell_join(["mkdir", "-p", out]),
            _shell_join(["ln", "-s", str(inputs.get("biobox_file", "")), "biobox.tsv"]),
            _shell_join(["ln", "-s", str(inputs.get(taxid_input, "")), staged_taxid]),
        ]
        commands.append(
            _shell_join(
                [
                    "biobox_add_taxid.py",
                    "biobox.tsv",
                    taxid_flag,
                    staged_taxid,
                    "-k_c",
                    str(inputs.get("key_col", "")),
                    "-t_c",
                    str(inputs.get("taxid_col", "")),
                ]
            )
        )
        commands.append(_shell_join(["cp", "modified_biobox_file.tsv", f"{out}/modified_biobox_file.tsv"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "modified_biobox_file.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "biobox_file": ("TSV", {"description": "Input CAMI AMBER biobox file"}),
                "input_mode": (
                    "STRING",
                    {"default": "contig", "options": cls.INPUT_MODES, "description": "Taxonomy mapping input type"},
                ),
                "key_col": ("INT", {"min": 1, "description": "Column containing contig or bin identifiers"}),
                "taxid_col": ("INT", {"min": 1, "description": "Column containing NCBI TaxIDs"}),
            },
            "optional": {
                "contig2taxid": ("TSV", {"default": "", "description": "ContigID2TaxID table, for contig mode"}),
                "binid2taxid": ("TSV", {"default": "", "description": "BinID2TaxID table, for bin mode"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("biobox_file", "")).strip():
            return "biobox_file is required"
        mode = cls._input_mode(inputs)
        if mode not in cls.INPUT_MODES:
            return f"input_mode must be one of: {', '.join(cls.INPUT_MODES)}"
        if mode == "contig" and not str(inputs.get("contig2taxid", "")).strip():
            return "contig2taxid is required when input_mode is contig"
        if mode == "bin" and not str(inputs.get("binid2taxid", "")).strip():
            return "binid2taxid is required when input_mode is bin"
        for name in ["key_col", "taxid_col"]:
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                return f"{name} is required"
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < 1:
                return f"{name} must be >= 1"
        return super().VALIDATE_INPUTS(inputs)

pin_contract(BioboxAddTaxidNode)

__all__ = ['BioboxAddTaxidNode']
