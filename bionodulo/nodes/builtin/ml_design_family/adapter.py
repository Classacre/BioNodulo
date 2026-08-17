"""Shared helpers for the pure-Python mRNA design-loop nodes."""

from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.base import BaseNode, path_probe_is_file

PYTHON_VERSION = "3.12"
STRATEGIES = ("synonymous_uniform", "synonymous_weighted", "gc_jitter")

CODON_AMINO_ACID: dict[str, str] = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}

AMINO_ACID_CODONS: dict[str, list[str]] = {}
for _codon, _aa in sorted(CODON_AMINO_ACID.items()):
    if _aa != "*":
        AMINO_ACID_CODONS.setdefault(_aa, []).append(_codon)


class MLDesignNode(BaseNode):
    """Metadata shared by BioNodulo's native mRNA design-loop nodes."""

    CATEGORY = "ml_design"
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_EXECUTABLES: ClassVar[list[str]] = []
    VERSION = "1.0.0"
    ENVIRONMENT = {"python": PYTHON_VERSION}


def path_value(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:  # noqa: BLE001
        return ""


def node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    output_dir = base / node.NODE_ID
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def existing_file(value: Any, key: str) -> Path:
    text = path_value(value)
    if not text:
        raise ValueError(f"Input '{key}' must be a non-empty path-like value")
    resolved = Path(text).expanduser()
    if not path_probe_is_file(text):
        raise ValueError(f"Input file does not exist: {resolved}")
    return resolved


def read_sequence_text(value: Any, key: str) -> str:
    text = path_value(value)
    if not text:
        return ""
    candidate = Path(text).expanduser()
    if path_probe_is_file(text):
        text = candidate.read_text(encoding="utf-8")
    return re.sub(r"\s+", "", re.sub(r"^>.*$", "", text, flags=re.MULTILINE)).upper()


def validate_dna(sequence: str, key: str) -> str:
    if not sequence:
        raise ValueError(f"Input '{key}' must be a non-empty DNA sequence")
    invalid = sorted({char for char in sequence if char not in "ACGT"})
    if invalid:
        raise ValueError(f"Input '{key}' contains non-ACGT character(s): {', '.join(invalid)}")
    if len(sequence) % 3 != 0:
        raise ValueError(f"Input '{key}' length must be a multiple of three (got {len(sequence)})")
    return sequence


def translate(cds: str, key: str) -> str:
    validate_dna(cds, key)
    protein: list[str] = []
    for index in range(0, len(cds), 3):
        amino_acid = CODON_AMINO_ACID.get(cds[index : index + 3])
        if amino_acid is None:
            raise ValueError(f"Input '{key}' contains unknown codon at position {index // 3}")
        protein.append(amino_acid)
    protein_str = "".join(protein)
    if "*" in protein_str:
        position = protein_str.index("*")
        raise ValueError(f"Input '{key}' contains a stop codon at CDS position {position}")
    return protein_str


def load_json_or_table(value: Any, key: str) -> tuple[Any, tuple[list[str], list[dict[str, str]]] | None]:
    """Return (json_payload, None) or (None, (fieldnames, rows)) for a TSV/CSV file."""
    text = path_value(value)
    if not text:
        return None, None
    candidate = Path(text).expanduser()
    if path_probe_is_file(text):
        content = candidate.read_text(encoding="utf-8").lstrip()
        if content.startswith(("{", "[")):
            try:
                return json.loads(content), None
            except json.JSONDecodeError as exc:
                raise ValueError(f"Input '{key}' is not valid JSON ({candidate}): {exc}") from exc
        return None, read_table(candidate)
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        raise ValueError(f"Input '{key}' must be a JSON/TSV file path or inline JSON: {exc}") from exc


def load_json_payload(value: Any, key: str) -> Any:
    text = path_value(value)
    if not text:
        return None
    candidate = Path(text).expanduser()
    if path_probe_is_file(text):
        try:
            return json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Input '{key}' is not valid JSON ({candidate}): {exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Input '{key}' must be a JSON file path or inline JSON: {exc}") from exc


def load_json_mapping(value: Any, key: str) -> dict[str, Any] | None:
    payload = load_json_payload(value, key)
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError(f"Input '{key}' must be a JSON object")
    return payload


def parse_candidates(value: Any, key: str = "candidates") -> list[dict[str, Any]]:
    payload = load_json_payload(value, key)
    if payload is None:
        raise ValueError(f"Input '{key}' is required")
    if isinstance(payload, dict) and isinstance(payload.get("candidates"), list):
        payload = payload["candidates"]
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"Input '{key}' must be a non-empty JSON array of candidate objects")
    seen: set[str] = set()
    entries: list[dict[str, Any]] = []
    for index, entry in enumerate(payload):
        if not isinstance(entry, dict):
            raise ValueError(f"Input '{key}' entry {index} must be a JSON object")
        identifier = str(entry.get("id", "")).strip()
        if not identifier:
            raise ValueError(f"Input '{key}' entry {index} is missing a non-empty 'id'")
        if identifier in seen:
            raise ValueError(f"Input '{key}' contains duplicate candidate id: {identifier}")
        seen.add(identifier)
        cds = path_value(entry.get("cds", ""))
        validate_dna(cds, f"{key}[{identifier}].cds")
        record = dict(entry)
        record["id"] = identifier
        record["cds"] = cds
        record["utr5"] = path_value(entry.get("utr5", ""))
        record["utr3"] = path_value(entry.get("utr3", ""))
        entries.append(record)
    lengths = {len(entry["cds"]) for entry in entries}
    if len(lengths) != 1:
        raise ValueError(f"Input '{key}' candidates must share one CDS length (got {sorted(lengths)})")
    return entries


def parse_score_entries(
    value: Any,
    key: str,
    score_field: str,
) -> list[dict[str, Any]]:
    payload = load_json_payload(value, key)
    if payload is not None:
        if not isinstance(payload, list) or not payload:
            raise ValueError(f"Input '{key}' must be a non-empty JSON array of {{id, {score_field}}}")
        return [dict(entry) for entry in payload]
    table_path = existing_file(value, key)
    _, rows = read_table(table_path)
    return rows


def read_table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    delimiter = "," if path.suffix.lower() == ".csv" else "\t"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        try:
            fieldnames = next(reader)
        except StopIteration as exc:
            raise ValueError(f"Table is empty: {path}") from exc
        if not fieldnames or any(not name.strip() for name in fieldnames):
            raise ValueError(f"Table header contains an empty column name: {path}")
        rows: list[dict[str, str]] = []
        for line_number, values in enumerate(reader, start=2):
            if not values:
                continue
            if len(values) != len(fieldnames):
                raise ValueError(f"Table row {line_number} has {len(values)} fields; expected {len(fieldnames)}")
            rows.append(dict(zip(fieldnames, values, strict=True)))
    if not rows:
        raise ValueError(f"Table contains no data rows: {path}")
    return [name.strip() for name in fieldnames], rows


def numeric_field(entry: dict[str, Any], field: str, context: str) -> float:
    if field not in entry or entry[field] in (None, ""):
        raise ValueError(f"{context} is missing numeric field '{field}'")
    value = entry[field]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        try:
            value = float(str(value).strip())
        except ValueError as exc:
            raise ValueError(f"{context} field '{field}' is not numeric: {entry[field]!r}") from exc
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{context} field '{field}' must be finite: {number}")
    return number


def write_json_file(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")


def write_tsv_file(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    if not fieldnames:
        raise ValueError("Output table must contain at least one column")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({name: format_cell(row.get(name, "")) for name in fieldnames})


def format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.6f}"
    return str(value)


def write_fasta_file(path: Path, records: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for identifier, sequence in records:
        lines.append(f">{identifier}")
        lines.extend(sequence[index : index + 60] for index in range(0, len(sequence), 60))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def softmax(values: list[float], temperature: float) -> list[float]:
    if temperature <= 0:
        raise ValueError("Temperature must be positive")
    top = max(values)
    exponentials = [math.exp((value - top) / temperature) for value in values]
    total = sum(exponentials)
    if total <= 0:
        n = len(values)
        return [1.0 / n] * n
    return [value / total for value in exponentials]


def validate_int_input(
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


def validate_float_input(
    value: Any,
    key: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> bool | str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return f"Input '{key}' must be a number"
    number = float(value)
    if not math.isfinite(number):
        return f"Input '{key}' must be finite"
    if minimum is not None and number < minimum:
        return f"Input '{key}' must be at least {minimum:g}"
    if maximum is not None and number > maximum:
        return f"Input '{key}' must be at most {maximum:g}"
    return True


def validate_choice_input(value: Any, key: str, choices: tuple[str, ...]) -> bool | str:
    if str(value) not in choices:
        return f"Input '{key}' must be one of: {', '.join(choices)}"
    return True
