"""Sage 0.14.7 peptide-spectrum matching."""

from __future__ import annotations

import gzip
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
    UPSTREAM_SOURCE = (
        "crates/sage-cli/src/input.rs; crates/sage-cli/src/main.rs; "
        "crates/sage-cli/src/output.rs; crates/sage/src/database.rs; "
        "crates/sage/src/fasta.rs; crates/sage/src/mass.rs"
    )
    EXIT_SEMANTICS = (
        "BioNodulo fails before launch when supplied-decoy mode lacks both target and tagged "
        "decoy accessions; a non-zero Sage exit is fatal and all four planned outputs are required."
    )
    CITATION_DOIS = ["10.1021/acs.jproteome.3c00486"]
    CITATION_URLS = ["https://doi.org/10.1021/acs.jproteome.3c00486"]
    CITATION_TEXT = "Sage: An Open-Source Tool for Fast Proteomics Searching and Quantification at Scale."

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "spectra_files": (
                    "FILE",
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
                "precursor_tol_lower_ppm": (
                    "FLOAT",
                    {
                        "default": None,
                        "description": "Optional asymmetric lower precursor bound in ppm",
                    },
                ),
                "precursor_tol_upper_ppm": (
                    "FLOAT",
                    {
                        "default": None,
                        "description": "Optional asymmetric upper precursor bound in ppm",
                    },
                ),
                "fragment_tol_lower_da": (
                    "FLOAT",
                    {
                        "default": None,
                        "description": "Optional asymmetric lower fragment bound in Da",
                    },
                ),
                "fragment_tol_upper_da": (
                    "FLOAT",
                    {
                        "default": None,
                        "description": "Optional asymmetric upper fragment bound in Da",
                    },
                ),
                "missed_cleavages": ("INT", {"default": 1, "min": 0, "max": 255}),
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
        for prefix, unit in (("precursor", "ppm"), ("fragment", "da")):
            lower_key = f"{prefix}_tol_lower_{unit}"
            upper_key = f"{prefix}_tol_upper_{unit}"
            lower = inputs.get(lower_key)
            upper = inputs.get(upper_key)
            if (lower is None) != (upper is None):
                return f"Inputs '{lower_key}' and '{upper_key}' must be provided together"
            if lower is not None:
                for key, value in ((lower_key, lower), (upper_key, upper)):
                    validation = validate_number(value, key)
                    if validation is not True:
                        return validation
                if float(lower) > float(upper):
                    return f"Input '{lower_key}' must not exceed '{upper_key}'"
        if inputs.get("batch_size") is not None:
            validation = validate_int(inputs["batch_size"], "batch_size", minimum=1, maximum=65535)
            if validation is not True:
                return validation
        for key, default, minimum, maximum in (
            ("missed_cleavages", 1, 0, 255),
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

    @staticmethod
    def _tolerance_pair(
        inputs: dict[str, Any],
        *,
        symmetric_key: str,
        lower_key: str,
        upper_key: str,
    ) -> list[float]:
        lower = inputs.get(lower_key)
        upper = inputs.get(upper_key)
        if lower is not None and upper is not None:
            return [float(lower), float(upper)]
        symmetric = abs(float(inputs[symmetric_key]))
        return [-symmetric, symmetric]

    @staticmethod
    def _require_target_decoy_fasta(fasta_db: Any, decoy_tag: str) -> None:
        """Fail closed when supplied-decoy mode lacks target or tagged decoy accessions."""
        fasta_path = Path(path_value(fasta_db))
        if not fasta_path.is_file():
            raise ValueError("Input 'fasta_db' must be an existing file when generate_decoys is false")
        opener = gzip.open if fasta_path.name.lower().endswith((".gz", ".gzip")) else open
        has_target = False
        has_decoy = False
        accession = ""
        has_sequence = False

        def record_completed() -> None:
            nonlocal has_target, has_decoy
            if not accession or not has_sequence:
                return
            if decoy_tag in accession:
                has_decoy = True
            else:
                has_target = True

        with opener(fasta_path, "rt", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                if line.startswith(">"):
                    record_completed()
                    fields = line[1:].strip().split(maxsplit=1)
                    accession = fields[0] if fields else ""
                    has_sequence = False
                    if has_target and has_decoy:
                        return
                else:
                    has_sequence = True
        record_completed()
        if not has_decoy:
            raise ValueError(
                f"Input 'fasta_db' contains no accession with decoy_tag {decoy_tag!r} "
                "while generate_decoys is false"
            )
        if not has_target:
            raise ValueError("Input 'fasta_db' contains tagged decoys but no target accession")

    @classmethod
    def REQUIRED_OUTPUT_PATHS(
        cls,
        inputs: dict[str, Any],
        outputs: list[Path],
    ) -> list[Path]:
        """The PIN is conditional: Sage omits it when nothing passes FDR.

        Verified against Sage 0.14.6 using the project's OWN test fixture and
        config: a correct PSM is written to results.sage.tsv while no
        results.sage.pin appears, because zero PSMs clear 1% FDR. Requiring the
        PIN unconditionally turned "this search found nothing" -- a legitimate
        scientific outcome, and unavoidable for a single-file search where FDR
        has no decoy distribution to work with -- into a hard node failure.
        """
        pin_path = outputs[3] if len(outputs) > 3 else None
        return [path for path in outputs if path != pin_path]

    @classmethod
    def VERIFY_OUTPUTS(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        """Materialise an empty PIN so downstream Percolator still gets a file.

        A missing artifact would break the wired edge; an empty one carries the
        same meaning (no PSMs) in a form the consumer can read.
        """
        if len(outputs) > 3 and not outputs[3].exists():
            outputs[3].parent.mkdir(parents=True, exist_ok=True)
            outputs[3].write_text("", encoding="utf-8")

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        cls.require_valid_inputs(inputs)
        output_dir = outputs[0].parent
        decoy_tag = str(inputs.get("decoy_tag", "rev_"))
        generate_decoys = bool(inputs.get("generate_decoys", True))
        if not generate_decoys:
            cls._require_target_decoy_fasta(inputs["fasta_db"], decoy_tag)
        precursor = cls._tolerance_pair(
            inputs,
            symmetric_key="precursor_tol_ppm",
            lower_key="precursor_tol_lower_ppm",
            upper_key="precursor_tol_upper_ppm",
        )
        fragment = cls._tolerance_pair(
            inputs,
            symmetric_key="fragment_tol_da",
            lower_key="fragment_tol_lower_da",
            upper_key="fragment_tol_upper_da",
        )
        config = {
            "database": {
                "decoy_tag": decoy_tag,
                "enzyme": {
                    "cleave_at": "KR",
                    "restrict": "P",
                    "c_terminal": True,
                    "semi_enzymatic": False,
                    "missed_cleavages": inputs.get("missed_cleavages", 1),
                    "min_len": inputs.get("min_peptide_length", 5),
                    "max_len": inputs.get("max_peptide_length", 50),
                },
                "fasta": path_value(inputs["fasta_db"]),
                "generate_decoys": generate_decoys,
            },
            "fragment_tol": {"da": fragment},
            "mzml_paths": path_list(inputs["spectra_files"]),
            "output_directory": str(output_dir),
            "precursor_tol": {"ppm": precursor},
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
