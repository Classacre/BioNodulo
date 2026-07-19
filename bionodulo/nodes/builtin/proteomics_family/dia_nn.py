"""DIA-NN 1.9.2 external-binary contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import ProteomicsCommandNode, path_list, path_value, validate_int, validate_number


class DIANNNode(ProteomicsCommandNode):
    """Analyze DIA runs with a supplied DIA-NN 1.9.2 Linux executable."""

    NODE_ID = "dia_nn"
    DISPLAY_NAME = "DIA-NN"
    DESCRIPTION = "Analyze DIA proteomics data with a user-supplied DIA-NN 1.9.2 executable."
    SEARCH_ALIASES = ["BioNodulo builtin", "DIA-NN", "DIA", "data independent acquisition"]
    RETURN_TYPES = ("TSV", "TSV")
    RETURN_NAMES = ("report", "stats")
    REQUIRED_EXECUTABLES = ["diann"]
    REQUIRED_CONDA_PACKAGES: list[str] = []
    REQUIRED_PATH_INPUTS = ("library", "fasta")
    REQUIRED_PATH_LIST_INPUTS = ("raw_files",)
    OUTPUT_FILENAMES = ("report.tsv", "report.stats.tsv")
    VERSION = "1.9.2"
    GIT_URL = "https://github.com/vdemichev/DiaNN.git"
    GIT_COMMIT = "af0e13d9eb3738c338dbbc4c61e6eb1d67d8bed8"
    DOCUMENTATION_URL = (
        "https://github.com/vdemichev/DiaNN/blob/"
        "af0e13d9eb3738c338dbbc4c61e6eb1d67d8bed8/README.md"
    )
    UPSTREAM_SOURCE = "DIA-NN 1.9.2 README command-line reference and release assets"
    INSTALLATION_REQUIRED = (
        "User-supplied DIA-NN 1.9.2 Linux distribution; no Bioconda or conda-forge package exists"
    )
    PACKAGE_CONSTRAINT = "external binary diann 1.9.2"
    CITATION_DOIS = ["10.1038/s41592-019-0638-x"]
    CITATION_URLS = ["https://doi.org/10.1038/s41592-019-0638-x"]
    CITATION_TEXT = "DIA-NN: neural networks and interference correction enable deep proteome coverage."

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "raw_files": (
                    "FILE_LIST",
                    {"multiple": True, "description": "One or more DIA spectrum files"},
                ),
                "library": ("FILE", {"description": "DIA-NN spectral library"}),
                "fasta": ("FASTA", {"description": "Protein FASTA database"}),
            },
            "optional": {
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
                "qvalue": ("FLOAT", {"default": 0.01, "min": 0.0, "max": 1.0}),
                "mass_accuracy": (
                    "FLOAT",
                    {"default": None, "min": 0.0, "description": "MS2 mass accuracy in ppm"},
                ),
                "use_predictor": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_int(inputs.get("threads", 4), "threads", minimum=1, maximum=128)
        if validation is not True:
            return validation
        validation = validate_number(inputs.get("qvalue", 0.01), "qvalue", minimum=0.0, maximum=1.0)
        if validation is not True:
            return validation
        if inputs.get("mass_accuracy") is not None:
            return validate_number(inputs["mass_accuracy"], "mass_accuracy", minimum=0.0)
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        output = Path(path_value(inputs.get("output", ".")))
        command = [
            "diann",
            "--lib",
            path_value(inputs["library"]),
            "--fasta",
            path_value(inputs["fasta"]),
            "--out",
            str(output / "report.tsv"),
            "--threads",
            str(inputs.get("threads", 4)),
            "--qvalue",
            str(inputs.get("qvalue", 0.01)),
        ]
        if inputs.get("mass_accuracy") is not None:
            command.extend(["--mass-acc", str(inputs["mass_accuracy"])])
        if inputs.get("use_predictor", False):
            command.append("--predictor")
        for raw_file in path_list(inputs["raw_files"]):
            command.extend(["--f", raw_file])
        return command


class DIANNAliasNode(DIANNNode):
    """Compatibility alias for the punctuation-free DIA-NN node ID."""

    NODE_ID = "diann"
    DISPLAY_NAME = "DIA-NN"
    DESCRIPTION = "Analyze DIA proteomics data with a user-supplied DIA-NN 1.9.2 executable."
    SEARCH_ALIASES = ["BioNodulo builtin", "diann", "DIA-NN", "DIA", "quantification"]
