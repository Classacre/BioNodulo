"""Percolator 3.7.1 PSM and protein rescoring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import ProteomicsCommandNode, path_value, validate_choice, validate_number


class PercolatorNode(ProteomicsCommandNode):
    """Rescore PIN PSMs and calculate picked-protein probabilities."""

    NODE_ID = "percolator"
    DISPLAY_NAME = "Percolator"
    DESCRIPTION = "Semi-supervised PSM rescoring and picked-protein inference with Percolator 3.7.1."
    SEARCH_ALIASES = ["BioNodulo builtin", "Percolator", "PSM rescoring", "false discovery rate"]
    RETURN_TYPES = ("TSV", "TSV")
    RETURN_NAMES = ("percolator_psms", "percolator_proteins")
    REQUIRED_EXECUTABLES = ["percolator"]
    REQUIRED_CONDA_PACKAGES = ["percolator"]
    REQUIRED_PATH_INPUTS = ("pin_file", "fasta_db")
    OUTPUT_FILENAMES = ("percolator_psms.tsv", "percolator_proteins.tsv")
    VERSION = "3.7.1"
    GIT_URL = "https://github.com/percolator/percolator.git"
    GIT_COMMIT = "310f92447357d6cb5132b4ee25f7640d7cff9eda"
    DOCUMENTATION_URL = "https://github.com/percolator/percolator/tree/rel-3-07-01"
    UPSTREAM_SOURCE = "src/Caller.cpp"
    CITATION_DOIS = ["10.1038/nmeth1113"]
    CITATION_URLS = ["https://doi.org/10.1038/nmeth1113"]
    CITATION_TEXT = "Semi-supervised learning for peptide identification from shotgun proteomics datasets."
    SEARCH_INPUTS = ("auto", "concatenated", "separate")
    PROTEIN_ENZYMES = (
        "no_enzyme",
        "elastase",
        "pepsin",
        "proteinasek",
        "thermolysin",
        "trypsinp",
        "chymotrypsin",
        "lys-n",
        "lys-c",
        "arg-c",
        "asp-n",
        "glu-c",
        "trypsin",
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "pin_file": ("FILE", {"description": "Percolator tab-delimited PIN input"}),
                "fasta_db": ("FASTA", {"description": "Protein FASTA used for picked-protein grouping"}),
            },
            "optional": {
                "search_input": ("STRING", {"default": "auto", "options": list(cls.SEARCH_INPUTS)}),
                "decoy_prefix": ("STRING", {"default": "auto", "description": "Protein decoy prefix or auto"}),
                "test_fdr": ("FLOAT", {"default": 0.01, "min": 0.0, "max": 1.0}),
                "train_fdr": ("FLOAT", {"default": 0.01, "min": 0.0, "max": 1.0}),
                "protein_enzyme": (
                    "STRING",
                    {"default": "trypsin", "options": list(cls.PROTEIN_ENZYMES)},
                ),
                "post_processing_tdc": (
                    "BOOLEAN",
                    {"default": False, "description": "Force target-decoy competition for separate-search PIN input"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_choice(inputs.get("search_input", "auto"), "search_input", cls.SEARCH_INPUTS)
        if validation is not True:
            return validation
        validation = validate_choice(
            inputs.get("protein_enzyme", "trypsin"),
            "protein_enzyme",
            cls.PROTEIN_ENZYMES,
        )
        if validation is not True:
            return validation
        if not str(inputs.get("decoy_prefix", "auto")).strip():
            return "Input 'decoy_prefix' must be non-empty"
        for key in ("test_fdr", "train_fdr"):
            validation = validate_number(inputs.get(key, 0.01), key, minimum=0.0, maximum=1.0)
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = [
            "percolator",
            "--results-psms",
            str(output / "percolator_psms.tsv"),
            "--picked-protein",
            path_value(inputs["fasta_db"]),
            "--results-proteins",
            str(output / "percolator_proteins.tsv"),
            "--protein-decoy-pattern",
            str(inputs.get("decoy_prefix", "auto")),
            "--protein-enzyme",
            str(inputs.get("protein_enzyme", "trypsin")),
            "--testFDR",
            str(inputs.get("test_fdr", 0.01)),
            "--trainFDR",
            str(inputs.get("train_fdr", 0.01)),
            "--search-input",
            str(inputs.get("search_input", "auto")),
        ]
        if inputs.get("post_processing_tdc", False):
            command.append("--post-processing-tdc")
        command.append(path_value(inputs["pin_file"]))
        return command
