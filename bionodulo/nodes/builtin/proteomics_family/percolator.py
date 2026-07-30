"""Percolator 3.7.1 PSM and picked-protein rescoring."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

from .adapter import ProteomicsCommandNode, path_value, validate_choice, validate_number


_PERCOLATOR_VERSION = "3.7.1"
_PERCOLATOR_TAG = "rel-3-07-01"
_PERCOLATOR_TAG_OBJECT = "93ea589f59bd3293d1b73b10db90ff88a9685840"
_PERCOLATOR_COMMIT = "310f92447357d6cb5132b4ee25f7640d7cff9eda"
_PERCOLATOR_SOURCE_ROOT = f"https://github.com/percolator/percolator/blob/{_PERCOLATOR_COMMIT}"
_SAGE_VERSION = "0.14.7"
_SAGE_COMMIT = "99407db6e3754b31a9b88b7316a0aee67293c93f"
_SAGE_SOURCE_ROOT = f"https://github.com/lazear/sage/blob/{_SAGE_COMMIT}"

_SAGE_PIN_REQUIRED_COLUMNS = ("SpecId", "Label", "ScanNr", "Peptide", "Proteins")
_SAGE_PIN_FILENAME = "sage.percolator.pin"
_NTERM_MOD = re.compile(r"^\[([^\[\]]+)\]-")
_CTERM_MOD = re.compile(r"-\[([^\[\]]+)\]$")


def _sage_peptide_for_picked_protein(value: str, *, line_number: int) -> str:
    """Render Sage's peptide syntax as a flanked Percolator peptide.

    Sage 0.14.7 writes no flanking residues.  This adapter is intentionally
    restricted to Sage's full-digest mode: ``-`` terminal markers make the
    termini enzymatic in Percolator while preserving the searched peptide.
    """

    peptide = value.strip()
    if not peptide:
        raise ValueError(f"Sage PIN line {line_number} has an empty Peptide field")
    if any(character in peptide for character in "\t\r\n"):
        raise ValueError(f"Sage PIN line {line_number} has an invalid Peptide field")

    # Percolator's PTM removal recognizes terminal modifications as n[...]
    # and c[...], whereas Sage serializes them as [...]- and -[...].
    peptide = _NTERM_MOD.sub(r"n[\1]", peptide, count=1)
    peptide = _CTERM_MOD.sub(r"c[\1]", peptide, count=1)
    if peptide.count("[") != peptide.count("]"):
        raise ValueError(f"Sage PIN line {line_number} has unbalanced peptide modification brackets")

    # Leave already native, fully flanked input untouched.  Sage 0.14.7 does
    # not emit this form, but accepting it keeps staging idempotent.
    if len(peptide) >= 5 and peptide[1] == "." and peptide[-2] == ".":
        return peptide
    return f"-.{peptide}.-"


def _sage_scan_number(value: str, *, line_number: int) -> str:
    """Return the integer scan number from a Sage PIN ScanNr field.

    Sage emits the native mzML spectrum identifier (``spectrum=2861``, or a
    Thermo ``controllerType=0 controllerNumber=1 scan=30069``), while Percolator
    requires a plain integer and aborts the entire run on anything else.
    """
    text = value.strip()
    if text.isdigit():
        return text
    matches = re.findall(r"(\d+)", text)
    if not matches:
        raise ValueError(
            f"Sage PIN line {line_number} ScanNr {value!r} contains no scan number"
        )
    return matches[-1]


def _prepare_sage_pin(source: Path, target: Path, *, decoy_prefix: str) -> None:
    """Convert Sage 0.14.7's documented PIN dialect to native Percolator tab input."""

    if not source.is_file():
        raise ValueError("Input 'pin_file' must be an existing file for Sage PIN staging")
    target.parent.mkdir(parents=True, exist_ok=True)

    with source.open("r", encoding="utf-8", newline="") as source_handle:
        reader = csv.reader(source_handle, delimiter="\t")
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError("Sage PIN input is empty") from exc

        missing = [column for column in _SAGE_PIN_REQUIRED_COLUMNS if column not in header]
        if missing:
            raise ValueError(f"Sage PIN header is missing required column(s): {', '.join(missing)}")
        if header[-1] != "Proteins":
            raise ValueError("Sage 0.14.7 PIN must end with the Proteins column")

        label_index = header.index("Label")
        peptide_index = header.index("Peptide")
        protein_index = header.index("Proteins")
        scan_index = header.index("ScanNr")

        with target.open("w", encoding="utf-8", newline="") as target_handle:
            writer = csv.writer(target_handle, delimiter="\t", lineterminator="\n")
            writer.writerow(header)
            row_count = 0
            for line_number, row in enumerate(reader, start=2):
                if not row or not any(field.strip() for field in row):
                    continue
                if len(row) != len(header):
                    raise ValueError(
                        f"Sage PIN line {line_number} has {len(row)} fields; expected {len(header)}"
                    )
                label = row[label_index].strip()
                if label not in {"1", "-1"}:
                    raise ValueError(f"Sage PIN line {line_number} Label must be 1 or -1")

                proteins = [protein.strip() for protein in row[protein_index].split(";")]
                if not proteins or any(not protein for protein in proteins):
                    raise ValueError(f"Sage PIN line {line_number} has an invalid Proteins field")
                if decoy_prefix != "auto":
                    prefixed = [protein.startswith(decoy_prefix) for protein in proteins]
                    if label == "-1" and not all(prefixed):
                        raise ValueError(
                            f"Sage PIN line {line_number} decoy proteins must start with {decoy_prefix!r}"
                        )
                    if label == "1" and any(prefixed):
                        raise ValueError(
                            f"Sage PIN line {line_number} target proteins must not start with {decoy_prefix!r}"
                        )

                # Percolator parses ScanNr as an INTEGER and aborts the whole
                # run with "error reading scan number on line N" otherwise. Sage
                # writes the mzML spectrum identifier there ("spectrum=2861"),
                # so pull the trailing integer out of it.
                row[scan_index] = _sage_scan_number(
                    row[scan_index],
                    line_number=line_number,
                )
                row[peptide_index] = _sage_peptide_for_picked_protein(
                    row[peptide_index],
                    line_number=line_number,
                )
                # Percolator's native default is one tab-delimited field per
                # protein after the Peptide field; Sage joins them with ';'.
                writer.writerow([*row[:protein_index], *proteins])
                row_count += 1

    if row_count == 0:
        target.unlink(missing_ok=True)
        raise ValueError("Sage PIN input contains no PSM rows")


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
    VERSION = _PERCOLATOR_VERSION
    GIT_URL = "https://github.com/percolator/percolator.git"
    GIT_COMMIT = _PERCOLATOR_COMMIT
    GIT_TAG = _PERCOLATOR_TAG
    GIT_TAG_OBJECT = _PERCOLATOR_TAG_OBJECT
    SOURCE_REF = f"annotated tag {_PERCOLATOR_TAG} at {_PERCOLATOR_COMMIT}"
    SOURCE_REVISION = _PERCOLATOR_COMMIT
    SOURCE_ARCHIVE_URL = (
        f"https://github.com/percolator/percolator/archive/refs/tags/{_PERCOLATOR_TAG}.tar.gz"
    )
    SOURCE_ARCHIVE_SHA256 = "f1c9833063cb4e99c51a632efc3f80c6b8f48a43fd440ea3eb0968af5c84b97a"
    SOURCE_PATHS = (
        "src/Caller.cpp",
        "src/main.cpp",
        "src/DataSet.cpp",
        "src/PSMDescription.cpp",
        "src/PSMDescription.h",
        "src/TabFileValidator.cpp",
    )
    SOURCE_URLS = tuple(f"{_PERCOLATOR_SOURCE_ROOT}/{path}" for path in SOURCE_PATHS)
    DOCUMENTATION_URL = SOURCE_URLS[0]
    UPSTREAM_SOURCE = "; ".join(SOURCE_PATHS)
    CONDA_PACKAGE_CONSTRAINTS = {"percolator": _PERCOLATOR_VERSION}
    PACKAGE_CONSTRAINTS = (f"percolator=={_PERCOLATOR_VERSION}",)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    AUDIT_STATUS = "contract-checked-no-external-execution"
    EXIT_SEMANTICS = (
        "Percolator main returns failure when option parsing or Caller::run fails and when an "
        "exception is caught; BioNodulo additionally requires both declared result files after "
        "a zero exit. Target peptide rows remain on captured stdout and diagnostics use stderr."
    )
    SAGE_COMPATIBILITY_VERSION = _SAGE_VERSION
    SAGE_COMPATIBILITY_COMMIT = _SAGE_COMMIT
    SAGE_COMPATIBILITY_SOURCE_URLS = (
        f"{_SAGE_SOURCE_ROOT}/crates/sage-cli/src/output.rs",
        f"{_SAGE_SOURCE_ROOT}/crates/sage/src/peptide.rs",
    )
    CITATION_DOIS = ["10.1038/nmeth1113"]
    CITATION_URLS = ["https://doi.org/10.1038/nmeth1113"]
    CITATION_TEXT = "Semi-supervised learning for peptide identification from shotgun proteomics datasets."
    SEARCH_INPUTS = ("auto", "concatenated", "separate")
    PIN_DIALECTS = ("native", "sage_0_14_7_full_digest")
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
                "pin_dialect": (
                    "STRING",
                    {
                        "default": "native",
                        "options": list(cls.PIN_DIALECTS),
                        "description": (
                            "Native Percolator PIN, or Sage 0.14.7 full-digest PIN requiring "
                            "flank and protein-field staging"
                        ),
                    },
                ),
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
        validation = validate_choice(inputs.get("pin_dialect", "native"), "pin_dialect", cls.PIN_DIALECTS)
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
        if not isinstance(inputs.get("decoy_prefix", "auto"), str):
            return "Input 'decoy_prefix' must be a string"
        if not str(inputs.get("decoy_prefix", "auto")).strip():
            return "Input 'decoy_prefix' must be non-empty"
        for key in ("test_fdr", "train_fdr"):
            validation = validate_number(inputs.get(key, 0.01), key, minimum=0.0, maximum=1.0)
            if validation is not True:
                return validation
        if not isinstance(inputs.get("post_processing_tdc", False), bool):
            return "Input 'post_processing_tdc' must be a boolean"
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        cls.require_valid_inputs(inputs)
        if inputs.get("pin_dialect", "native") != "sage_0_14_7_full_digest":
            return
        staged_pin = outputs[0].parent / _SAGE_PIN_FILENAME
        _prepare_sage_pin(
            Path(path_value(inputs["pin_file"])),
            staged_pin,
            decoy_prefix=str(inputs.get("decoy_prefix", "auto")),
        )
        inputs["pin_file"] = str(staged_pin)

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
