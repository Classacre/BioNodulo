"""Focused binning refiner node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin._variant_assembly_contracts import pin_contract

class BinningRefinerNode(CommandNode):
    """Improve metagenome bins by combining outputs from multiple binning programs."""

    NODE_ID = "bin_refiner"
    DISPLAY_NAME = "Binning refiner"
    REQUIRED_CONDA_PACKAGES = ["binning_refiner"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Refine metagenome bins from one or more FASTA bin sets and report refined-bin membership and source lengths."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Binning refiner",
        "Binning_refiner",
        "Binning refiner metagenome bins",
        "bin_refiner",
        "genome bins",
        "metagenome bin refinement",
        "contamination reduction",
        "refined bins",
    ]
    RETURN_TYPES = ("DIRECTORY", "TSV", "TSV")
    RETURN_NAMES = ("refined_bins", "refined_contigs", "sources_and_length")
    REQUIRED_EXECUTABLES = ["Binning_refiner"]
    DOCUMENTATION_URL = "https://github.com/songweizhi/Binning_refiner"
    CITATION_DOIS = ["10.1093/bioinformatics/btx086"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/btx086"]
    CITATION_TEXT = "Binning_refiner improves genome bins through the combination of different binning programs."
    VERSION = "1.4.3"
    SHELL = True

    @classmethod
    def _input_bins(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("input_bins", inputs.get("bins")))

    @classmethod
    def _element_identifiers(cls, inputs: dict[str, Any], input_bins: list[str]) -> list[str]:
        identifiers = _as_list(inputs.get("element_identifiers", inputs.get("identifiers")))
        return [
            _safe_identifier(identifiers[index]) if index < len(identifiers) and identifiers[index] else _safe_name(input_bin)
            for index, input_bin in enumerate(input_bins)
        ]

    @classmethod
    def _input_exts(cls, inputs: dict[str, Any], input_bins: list[str]) -> list[str]:
        raw_exts = _as_list(inputs.get("input_exts", inputs.get("exts")))
        exts: list[str] = []
        for index, input_bin in enumerate(input_bins):
            if index < len(raw_exts) and raw_exts[index]:
                ext = raw_exts[index].lstrip(".")
            else:
                suffixes = "".join(Path(input_bin).suffixes).lstrip(".")
                ext = suffixes or "fasta"
            exts.append(ext)
        return exts

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_dir = f"{out}/input_bin_dir"
        bins_dir = f"{input_dir}/bins"
        output_root = f"{out}/refined_Binning_refiner_outputs"
        input_bins = cls._input_bins(inputs)
        identifiers = cls._element_identifiers(inputs, input_bins)
        input_exts = cls._input_exts(inputs, input_bins)
        commands = [_shell_join(["mkdir", "-p", bins_dir])]
        for index, input_bin in enumerate(input_bins):
            staged = f"{bins_dir}/{identifiers[index]}.{input_exts[index]}"
            if input_exts[index].endswith(".gz") or input_exts[index].endswith("gz") or input_bin.endswith(".gz"):
                commands.append(f"gunzip -c {shlex.quote(input_bin)} > {shlex.quote(staged)}")
            else:
                commands.append(_shell_join(["ln", "-s", input_bin, staged]))
        commands.extend(
            [
                _shell_join(["Binning_refiner", "-i", input_dir, "-p", "refined", "-m", str(inputs.get("m", 512))]),
                _shell_join(["mv", f"{output_root}/refined_contigs.txt", f"{out}/refined_contigs.tsv"]),
                _shell_join(["mv", f"{output_root}/refined_sources_and_length.txt", f"{out}/sources_and_length.tsv"]),
            ]
        )
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        refined_bins = out / "refined_Binning_refiner_outputs" / "refined_refined_bins"
        refined_bins.mkdir(parents=True, exist_ok=True)
        return [refined_bins, out / "refined_contigs.tsv", out / "sources_and_length.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bins": (
                    "FASTA_LIST",
                    {
                        "multiple": True,
                        "description": "Binned FASTA or FASTA.GZ files produced by metagenome binning tools",
                    },
                ),
            },
            "optional": {
                "m": (
                    "INT",
                    {"default": 512, "min": 1, "description": "Minimum size in Kbp for a refined bin to be retained"},
                ),
                "element_identifiers": (
                    "STRING",
                    {"default": [], "multiple": True, "advanced": True, "description": "Optional Galaxy collection element names"},
                ),
                "input_exts": (
                    "STRING",
                    {"default": [], "multiple": True, "advanced": True, "description": "Optional datatype extensions for staged bins"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_bins(inputs):
            return "at least one binned FASTA is required"
        if int(inputs.get("m", 512)) < 1:
            return "minimum refined bin size must be >= 1 Kbp"
        return super().VALIDATE_INPUTS(inputs)

pin_contract(BinningRefinerNode)

__all__ = ['BinningRefinerNode']
