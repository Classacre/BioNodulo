"""Sage 0.14.7 peptide-spectrum matching."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .adapter import ProteomicsCommandNode, path_list, path_value, validate_int, validate_number


class SageSearchNode(ProteomicsCommandNode):
    """Search one or more mass-spectrometry files and emit a Percolator PIN file."""

    NODE_ID = "sage_search"
    DISPLAY_NAME = "Sage Search"
    DESCRIPTION = "Peptide-spectrum matching with Sage 0.14.7 and native PIN output."
    SEARCH_ALIASES = ["BioNodulo builtin", "Sage", "peptide spectrum matching", "proteomics search"]
    RETURN_TYPES = ("TSV", "JSON", "JSON", "FILE")
    RETURN_NAMES = ("results_tsv", "results_json", "config_json", "pin_file")
    REQUIRED_EXECUTABLES = ["sage"]
    REQUIRED_CONDA_PACKAGES = ["sage-proteomics"]
    REQUIRED_PATH_INPUTS = ("fasta_db",)
    REQUIRED_PATH_LIST_INPUTS = ("spectra_files",)
    OUTPUT_FILENAMES = ("results.sage.tsv", "results.json", "sage_config.json", "results.sage.pin")
    VERSION = "0.14.7"
    GIT_URL = "https://github.com/lazear/sage.git"
    GIT_COMMIT = "99407db6e3754b31a9b88b7316a0aee67293c93f"
    DOCUMENTATION_URL = "https://github.com/lazear/sage/blob/v0.14.7/DOCS.md"
    UPSTREAM_SOURCE = "crates/sage-cli/src/input.rs; main.rs; output.rs; crates/sage/src/database.rs"
    CITATION_DOIS = ["10.1021/acs.jproteome.3c00486"]
    CITATION_URLS = ["https://doi.org/10.1021/acs.jproteome.3c00486"]
    CITATION_TEXT = "Sage: An Open-Source Tool for Fast Proteomics Searching and Quantification at Scale."

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "spectra_files": (
                    "FILE_LIST",
                    {"multiple": True, "description": "One or more mzML, mzML.gz, MGF, or Bruker TDF inputs"},
                ),
                "fasta_db": ("FASTA", {"description": "Protein FASTA database"}),
                "precursor_tol_ppm": ("FLOAT", {"min": 0.0, "description": "Symmetric precursor tolerance in ppm"}),
                "fragment_tol_da": ("FLOAT", {"min": 0.0, "description": "Symmetric fragment tolerance in Da"}),
            },
            "optional": {
                "batch_size": (
                    "INT",
                    {"default": None, "min": 1, "max": 65535, "description": "Files loaded and searched in parallel"},
                ),
                "missed_cleavages": ("INT", {"default": 0, "min": 0, "max": 255}),
                "min_peptide_length": ("INT", {"default": 5, "min": 1}),
                "max_peptide_length": ("INT", {"default": 50, "min": 1}),
                "decoy_tag": ("STRING", {"default": "rev_", "description": "Substring identifying decoy accessions"}),
                "generate_decoys": (
                    "BOOLEAN",
                    {"default": True, "description": "Ignore tagged FASTA decoys and generate reversed peptide decoys"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("precursor_tol_ppm", "fragment_tol_da"):
            validation = validate_number(inputs.get(key), key, minimum=0.0)
            if validation is not True:
                return validation
        if inputs.get("batch_size") is not None:
            validation = validate_int(inputs["batch_size"], "batch_size", minimum=1, maximum=65535)
            if validation is not True:
                return validation
        for key, default, minimum, maximum in (
            ("missed_cleavages", 0, 0, 255),
            ("min_peptide_length", 5, 1, None),
            ("max_peptide_length", 50, 1, None),
        ):
            validation = validate_int(inputs.get(key, default), key, minimum=minimum, maximum=maximum)
            if validation is not True:
                return validation
        if inputs.get("min_peptide_length", 5) > inputs.get("max_peptide_length", 50):
            return "Input 'min_peptide_length' must not exceed 'max_peptide_length'"
        if not str(inputs.get("decoy_tag", "rev_")).strip():
            return "Input 'decoy_tag' must be non-empty"
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        cls.require_valid_inputs(inputs)
        output_dir = outputs[0].parent
        precursor = abs(float(inputs["precursor_tol_ppm"]))
        fragment = abs(float(inputs["fragment_tol_da"]))
        config = {
            "database": {
                "decoy_tag": str(inputs.get("decoy_tag", "rev_")),
                "enzyme": {
                    "cleave_at": "KR",
                    "restrict": "P",
                    "c_terminal": True,
                    "semi_enzymatic": False,
                    "missed_cleavages": inputs.get("missed_cleavages", 0),
                    "min_len": inputs.get("min_peptide_length", 5),
                    "max_len": inputs.get("max_peptide_length", 50),
                },
                "fasta": path_value(inputs["fasta_db"]),
                "generate_decoys": inputs.get("generate_decoys", True),
            },
            "fragment_tol": {"da": [-fragment, fragment]},
            "mzml_paths": path_list(inputs["spectra_files"]),
            "output_directory": str(output_dir),
            "precursor_tol": {"ppm": [-precursor, precursor]},
            "write_pin": True,
        }
        outputs[2].write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        inputs["_sage_config_path"] = str(outputs[2])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        config_path = str(
            inputs.get(
                "_sage_config_path",
                Path(str(inputs.get("output", inputs.get("output_dir", ".")))) / "sage_config.json",
            )
        )
        command = ["sage"]
        if inputs.get("batch_size") is not None:
            command.extend(["--batch-size", str(inputs["batch_size"])])
        command.append(config_path)
        return command
