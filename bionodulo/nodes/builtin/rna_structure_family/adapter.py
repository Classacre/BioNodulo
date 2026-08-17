"""Shared contracts for ViennaRNA secondary-structure command nodes."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


VIENNA_RNA_PACKAGE_VERSION = "2.7.0"
VIENNA_RNA_DOCUMENTATION_URL = "https://www.tbi.univie.ac.at/RNA/"
VIENNA_RNA_CITATION_DOI = "10.1186/1748-7182-6-26"
VIENNA_RNA_CITATION_TEXT = "ViennaRNA Package 2.0."

MAX_SEQUENCE_LENGTH = 50000
SEQUENCE_ALPHABET = frozenset("ACGTUN")
STAGING_FILENAME = "input.fasta"

_ENERGY_LINE_RE = re.compile(r"^([\.\(\)\[\]{}&]+)\s*\(\s*(-?\d+(?:\.\d+)?)\s*(?:=\s*(-?\d+(?:\.\d+)?)\s*\+\s*(-?\d+(?:\.\d+)?)\s*)?\)\s*$")
_ENSEMBLE_STATS_RE = re.compile(
    r"frequency of mfe structure in ensemble\s+([0-9.]+);\s*ensemble diversity\s+([0-9.]+)"
)
_ENSEMBLE_FREE_ENERGY_RE = re.compile(r"free energy of ensemble\s*=?\s*(-?\d+(?:\.\d+)?)")


def validate_int(
    value: Any,
    key: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> bool | str:
    if isinstance(value, bool) or not isinstance(value, int):
        return f"Input '{key}' must be an integer"
    if minimum is not None and value < minimum:
        return f"Input '{key}' must be at least {minimum}"
    if maximum is not None and value > maximum:
        return f"Input '{key}' must be at most {maximum}"
    return True


def validate_number(
    value: Any,
    key: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> bool | str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return f"Input '{key}' must be a number"
    number = float(value)
    if minimum is not None and number < minimum:
        return f"Input '{key}' must be at least {minimum:g}"
    if maximum is not None and number > maximum:
        return f"Input '{key}' must be at most {maximum:g}"
    return True


def validate_sequence_string(value: Any, key: str, *, max_length: int = MAX_SEQUENCE_LENGTH) -> bool | str:
    """Validate one inline RNA/DNA sequence parameter."""
    if not isinstance(value, str) or not value.strip():
        return f"Input '{key}' must be a non-empty sequence string"
    sequence = normalize_sequence(value)
    if not sequence:
        return f"Input '{key}' must be a non-empty sequence string"
    invalid = set(sequence) - SEQUENCE_ALPHABET
    if invalid:
        return (
            f"Input '{key}' is neither an existing FASTA file nor a valid RNA/DNA sequence "
            f"(non-ACGTUN characters: {''.join(sorted(invalid))})"
        )
    if len(sequence) > max_length:
        return f"Input '{key}' exceeds the {max_length} nt per-sequence limit ({len(sequence)} nt)"
    return True


def normalize_sequence(value: str) -> str:
    """Uppercase an RNA/DNA string and drop all whitespace and digits."""
    return "".join(char for char in str(value).upper() if char.isalpha())


def sequence_records(text: str) -> list[tuple[str, str]]:
    """Parse FASTA text (or one bare sequence) into (id, sequence) records."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    records: list[tuple[str, str]] = []
    header = ""
    chunks: list[str] = []
    for line in lines:
        if line.startswith(">"):
            if header or chunks:
                records.append((header, normalize_sequence("".join(chunks))))
            header = line[1:].strip().split()[0] if len(line) > 1 else "sequence"
            chunks = []
        elif line.startswith(";"):
            continue
        else:
            chunks.append(line)
    if header or chunks:
        records.append((header, normalize_sequence("".join(chunks))))
    if not records:
        raise ValueError("Input contains no RNA sequence")
    return records


def check_records(records: Iterable[tuple[str, str]], *, max_length: int = MAX_SEQUENCE_LENGTH) -> None:
    """Fail closed on empty or oversized records."""
    for record_id, sequence in records:
        if not sequence:
            raise ValueError(f"Sequence record '{record_id or 'sequence'}' is empty")
        if len(sequence) > max_length:
            raise ValueError(
                f"Sequence record '{record_id or 'sequence'}' exceeds the "
                f"{max_length} nt per-sequence limit ({len(sequence)} nt)"
            )
        invalid = set(sequence) - SEQUENCE_ALPHABET
        if invalid:
            raise ValueError(
                f"Sequence record '{record_id or 'sequence'}' contains non-RNA characters: "
                f"{''.join(sorted(invalid))}"
            )


def parse_fold_stdout(stdout: str, *, partition: bool) -> list[dict[str, Any]]:
    """Parse RNAfold stdout into per-record structure dictionaries."""
    records: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in stdout.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.startswith(">"):
            if current is not None:
                records.append(current)
            current = {"id": line[1:].strip().split()[0] if len(line) > 1 else "sequence"}
            continue
        stats = _ENSEMBLE_STATS_RE.search(line)
        if stats and current is not None:
            current["frequency_of_mfe"] = float(stats.group(1))
            current["ensemble_diversity"] = float(stats.group(2))
            continue
        match = _ENERGY_LINE_RE.match(line.strip())
        if match and current is not None:
            structure = match.group(1)
            if "sequence" not in current:
                continue
            entry = {
                "structure": structure,
                "energy": float(match.group(2)),
            }
            if match.group(3) is not None:
                entry["energy_centroid"] = float(match.group(3))
                entry["energy_correction"] = float(match.group(4))
            if "mfe" not in current:
                current["mfe"] = entry
            else:
                current["centroid"] = entry
            continue
        if current is not None and "sequence" not in current:
            candidate = normalize_sequence(line)
            if candidate and not set(candidate) - SEQUENCE_ALPHABET:
                current["sequence"] = candidate
    if current is not None:
        records.append(current)
    for record in records:
        if "mfe" not in record:
            raise ValueError(f"RNAfold produced no structure line for record '{record.get('id', 'sequence')}'")
        if partition and "centroid" not in record:
            raise ValueError(f"RNAfold -p produced no centroid structure for record '{record.get('id', 'sequence')}'")
    return records


def ensemble_free_energy(*texts: str) -> float | None:
    """Extract the ensemble free energy from stdout/stderr text when present."""
    for text in texts:
        match = _ENSEMBLE_FREE_ENERGY_RE.search(text)
        if match:
            return float(match.group(1))
    return None


def parse_lunp(path: Path) -> list[dict[str, Any]]:
    """Parse one RNAplfold ``*_lunp`` unpaired-probability file."""
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = stripped.split()
        try:
            numbers = [float(field) for field in fields]
        except ValueError:
            continue
        if len(numbers) < 2:
            continue
        position = int(numbers[0])
        probabilities = numbers[1:]
        rows.append(
            {
                "position": position,
                "p_unpaired": probabilities[0],
                "mean_p_unpaired": sum(probabilities) / len(probabilities),
            }
        )
    if not rows:
        raise ValueError(f"RNAplfold accessibility file is empty or malformed: {path}")
    return rows


class RNAStructureCommandNode(CommandNode):
    """ViennaRNA 2.7 contracts: pinned metadata, sequence validation, staging."""

    CATEGORY = "rna_structure"
    SHELL = False
    VERSION = VIENNA_RNA_PACKAGE_VERSION
    REQUIRED_CONDA_PACKAGES = ["vienna-rna"]
    CONDA_PACKAGE_CONSTRAINTS = {"vienna-rna": f">={VIENNA_RNA_PACKAGE_VERSION}"}
    PACKAGE_CONSTRAINT = f"vienna-rna >={VIENNA_RNA_PACKAGE_VERSION}"
    GIT_URL = ""
    GIT_COMMIT = ""
    DOCUMENTATION_URL = VIENNA_RNA_DOCUMENTATION_URL
    CITATION_DOIS = [VIENNA_RNA_CITATION_DOI]
    CITATION_URLS = [f"https://doi.org/{VIENNA_RNA_CITATION_DOI}"]
    CITATION_TEXT = VIENNA_RNA_CITATION_TEXT
    EXIT_SEMANTICS = (
        "ViennaRNA executables exit non-zero on unreadable input or malformed sequences; "
        "BioNodulo additionally fails when a planned structure or JSON artifact is missing."
    )
    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()
    REQUIRED_SEQUENCE_INPUTS: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / filename for filename in cls.OUTPUT_FILENAMES]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not cls.REQUIRED_SEQUENCE_INPUTS:
            return True
        provided = [
            key for key in cls.REQUIRED_SEQUENCE_INPUTS if inputs.get(key) not in (None, "")
        ]
        if len(provided) != 1:
            names = "' or '".join(cls.REQUIRED_SEQUENCE_INPUTS)
            return f"Provide exactly one of '{names}'"
        for key in provided:
            value = inputs.get(key)
            if Path(str(value)).is_file():
                continue
            validation = validate_sequence_string(value, key)
            if validation is not True:
                return validation
        return True

    @classmethod
    def resolve_sequence_source(cls, inputs: Mapping[str, Any]) -> tuple[str, str]:
        """Return (source path or '', fasta text) for the configured sequence input."""
        for key in cls.REQUIRED_SEQUENCE_INPUTS:
            value = inputs.get(key)
            if value in (None, ""):
                continue
            text = str(value)
            source = Path(text)
            if source.is_file():
                return str(source), source.read_text(encoding="utf-8")
            sequence = normalize_sequence(text)
            validation = validate_sequence_string(text, key)
            if validation is not True:
                raise ValueError(str(validation))
            return "", f">{cls.NODE_ID}\n{sequence}\n"
        names = "' or '".join(cls.REQUIRED_SEQUENCE_INPUTS)
        raise ValueError(f"Provide exactly one of '{names}'")

    @classmethod
    def staged_input_path(cls, inputs: Mapping[str, Any]) -> Path:
        """Return the deterministic in-node-dir FASTA path used for execution."""
        staged = inputs.get("_staged_fasta")
        if staged:
            return Path(str(staged))
        for key in cls.REQUIRED_SEQUENCE_INPUTS:
            value = inputs.get(key)
            if value not in (None, "") and Path(str(value)).is_file():
                return Path(str(value))
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        return Path(output) / cls.NODE_ID / STAGING_FILENAME

    @classmethod
    def stage_input(cls, inputs: dict[str, Any], outputs: list[Path]) -> Path:
        """Validate the sequence source and stage a FASTA inside the node dir."""
        del outputs
        source, fasta_text = cls.resolve_sequence_source(inputs)
        records = sequence_records(fasta_text)
        check_records(records)
        if cls.SINGLE_RECORD_INPUT and len(records) != 1:
            raise ValueError(
                f"Input '{cls.REQUIRED_SEQUENCE_INPUTS[0]}' must contain exactly one sequence "
                f"record ({len(records)} given)"
            )
        node_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        node_dir.mkdir(parents=True, exist_ok=True)
        staged = node_dir / STAGING_FILENAME
        if not source or Path(source).resolve() != staged.resolve():
            staged.write_text(fasta_text, encoding="utf-8")
        inputs["_staged_fasta"] = str(staged)
        return staged

    SINGLE_RECORD_INPUT: ClassVar[bool] = False

    @classmethod
    def checked_command(cls, inputs: dict[str, Any], *prefix: str) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        return list(prefix)
