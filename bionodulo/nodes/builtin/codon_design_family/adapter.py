"""Shared genetic-code, codon-usage, and validation helpers for codon design nodes."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.base import BaseNode, path_probe_is_file


CODON_USAGE_SOURCE = (
    "Rounded relative synonymous usage frequencies for Homo sapiens from the "
    "Kazusa Codon Usage Database (Nakamura et al. 2000, doi:10.1093/nar/28.1.292)"
)
KAZUSA_URL = "https://www.kazusa.or.jp/codon/cgi-bin/showcods.cgi?species=Homo+sapiens+%5B9606%5D"


def _codon_table(entries: tuple[tuple[str, str], ...]) -> dict[str, str]:
    table: dict[str, str] = {}
    for codons, amino in entries:
        for codon in codons.split():
            table[codon] = amino
    return table


DNA_CODON_TABLE: dict[str, str] = _codon_table(
    (
        ("TTT TTC", "F"),
        ("TTA TTG CTT CTC CTA CTG", "L"),
        ("ATT ATC ATA", "I"),
        ("ATG", "M"),
        ("GTT GTC GTA GTG", "V"),
        ("TCT TCC TCA TCG AGT AGC", "S"),
        ("CCT CCC CCA CCG", "P"),
        ("ACT ACC ACA ACG", "T"),
        ("GCT GCC GCA GCG", "A"),
        ("TAT TAC", "Y"),
        ("TAA TAG TGA", "*"),
        ("CAT CAC", "H"),
        ("CAA CAG", "Q"),
        ("AAT AAC", "N"),
        ("AAA AAG", "K"),
        ("GAT GAC", "D"),
        ("GAA GAG", "E"),
        ("TGT TGC", "C"),
        ("TGG", "W"),
        ("CGT CGC CGA CGG AGA AGG", "R"),
        ("GGT GGC GGA GGG", "G"),
    )
)

HUMAN_CODON_USAGE: dict[str, float] = {
    "TTT": 0.46, "TTC": 0.54,
    "TTA": 0.08, "TTG": 0.13, "CTT": 0.13, "CTC": 0.20, "CTA": 0.08, "CTG": 0.38,
    "ATT": 0.36, "ATC": 0.47, "ATA": 0.17, "ATG": 1.00,
    "GTT": 0.19, "GTC": 0.26, "GTA": 0.12, "GTG": 0.43,
    "TCT": 0.19, "TCC": 0.23, "TCA": 0.15, "TCG": 0.05, "AGT": 0.15, "AGC": 0.23,
    "CCT": 0.29, "CCC": 0.33, "CCA": 0.26, "CCG": 0.12,
    "ACT": 0.25, "ACC": 0.36, "ACA": 0.27, "ACG": 0.12,
    "GCT": 0.27, "GCC": 0.39, "GCA": 0.24, "GCG": 0.11,
    "TAT": 0.45, "TAC": 0.55,
    "CAT": 0.43, "CAC": 0.57,
    "CAA": 0.26, "CAG": 0.74,
    "AAT": 0.47, "AAC": 0.53,
    "AAA": 0.43, "AAG": 0.57,
    "GAT": 0.47, "GAC": 0.53,
    "GAA": 0.42, "GAG": 0.58,
    "TGT": 0.45, "TGC": 0.55,
    "TGG": 1.00,
    "CGT": 0.09, "CGC": 0.19, "CGA": 0.11, "CGG": 0.20, "AGA": 0.21, "AGG": 0.20,
    "GGT": 0.17, "GGC": 0.34, "GGA": 0.25, "GGG": 0.24,
}

STOP_CODONS = frozenset({"TAA", "TAG", "TGA"})
CAI_EXCLUDED_AMINO_ACIDS = frozenset({"M", "W", "*"})

AMINO_ACID_SYNONYMS: dict[str, tuple[str, ...]] = {}
for _codon, _amino in DNA_CODON_TABLE.items():
    if _amino == "*":
        continue
    AMINO_ACID_SYNONYMS.setdefault(_amino, [])
    AMINO_ACID_SYNONYMS[_amino] = (*AMINO_ACID_SYNONYMS[_amino], _codon)
AMINO_ACID_SYNONYMS = {amino: tuple(sorted(codons)) for amino, codons in AMINO_ACID_SYNONYMS.items()}

CODON_FAMILIES: tuple[tuple[str, ...], ...] = tuple(sorted(family) for family in AMINO_ACID_SYNONYMS.values())

# Wright's Nc treats 6-fold families (Leu, Ser, Arg) as their 2+4 subfamilies.
NC_SPLIT_FAMILIES: tuple[tuple[str, ...], ...] = (
    ("TTT", "TTC"), ("TAT", "TAC"), ("CAT", "CAC"), ("CAA", "CAG"),
    ("AAT", "AAC"), ("AAA", "AAG"), ("GAT", "GAC"), ("GAA", "GAG"),
    ("TGT", "TGC"), ("TTA", "TTG"), ("AGA", "AGG"), ("AGT", "AGC"),
    ("GTT", "GTC", "GTA", "GTG"), ("CCT", "CCC", "CCA", "CCG"),
    ("ACT", "ACC", "ACA", "ACG"), ("GCT", "GCC", "GCA", "GCG"),
    ("GGT", "GGC", "GGA", "GGG"), ("CTT", "CTC", "CTA", "CTG"),
    ("CGT", "CGC", "CGA", "CGG"), ("TCT", "TCC", "TCA", "TCG"),
    ("ATT", "ATC", "ATA"),
)

DNA_ALPHABET = frozenset("ACGT")
RNA_ALPHABET = frozenset("ACGU")
RNA_COMPLEMENT = str.maketrans("ACGU", "UGCA")


def to_dna(sequence: str) -> str:
    return sequence.replace("U", "T")


def to_rna(sequence: str) -> str:
    return sequence.replace("T", "U")


def reverse_complement_rna(sequence: str) -> str:
    return sequence.translate(RNA_COMPLEMENT)[::-1]


def read_sequence_input(value: Any, key: str) -> str:
    """Read one sequence from a literal string or a FASTA/plain-text file path."""
    text = str(value or "")
    if not text.strip():
        raise ValueError(f"Input '{key}' must be a non-empty sequence or file path")
    path = Path(text)
    if path.is_file():
        text = path.read_text(encoding="utf-8")
    pieces: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(">") or stripped.startswith(";"):
            continue
        pieces.append(stripped)
    return "".join(pieces).upper().replace(" ", "").replace("-", "")


def validate_sequence_literal(
    value: Any,
    key: str,
    *,
    alphabet: frozenset[str],
    divisible_by_3: bool = False,
) -> bool | str:
    """Validate an inline sequence literal; existing files are validated at run time."""
    text = str(value or "")
    if not text.strip():
        return f"Input '{key}' must be a non-empty sequence or file path"
    if path_probe_is_file(text) or text.startswith((">", ";")):
        return True
    sequence = "".join(text.split()).upper()
    if alphabet is DNA_ALPHABET:
        sequence = sequence.replace("U", "T")
    invalid = set(sequence) - alphabet
    if invalid:
        return f"Input '{key}' contains invalid characters: {''.join(sorted(invalid))}"
    if divisible_by_3 and len(sequence) % 3 != 0:
        return f"Input '{key}' length must be divisible by 3 ({len(sequence)} nt)"
    return True


def require_dna_cds(sequence: str, key: str) -> str:
    """Fail closed unless the sequence is a non-empty ACGT coding sequence."""
    if not sequence:
        raise ValueError(f"Input '{key}' is empty")
    invalid = set(sequence) - DNA_ALPHABET
    if invalid:
        raise ValueError(f"Input '{key}' contains non-ACGT characters: {''.join(sorted(invalid))}")
    if len(sequence) % 3 != 0:
        raise ValueError(f"Input '{key}' length must be divisible by 3 ({len(sequence)} nt)")
    return sequence


def codons_of(cds: str) -> list[str]:
    usable = len(cds) - len(cds) % 3
    return [cds[offset:offset + 3] for offset in range(0, usable, 3)]


def translate_cds(cds: str) -> str:
    return "".join(DNA_CODON_TABLE.get(codon, "X") for codon in codons_of(cds))


def gc_fraction(sequence: str) -> float:
    if not sequence:
        return 0.0
    return sum(1 for base in sequence if base in "GC") / len(sequence)


def gc_by_codon_position(cds: str) -> dict[str, float]:
    positions: dict[str, list[str]] = {"1": [], "2": [], "3": []}
    for offset in range(0, len(cds) - 2, 3):
        for index in (1, 2, 3):
            positions[str(index)].append(cds[offset + index - 1])
    return {frame: gc_fraction(bases) for frame, bases in positions.items()}


def relative_adaptiveness(usage: dict[str, float] | None = None) -> dict[str, float]:
    table = usage or HUMAN_CODON_USAGE
    weights: dict[str, float] = {}
    for family in CODON_FAMILIES:
        best = max(table.get(codon, 0.0) for codon in family)
        for codon in family:
            weights[codon] = table.get(codon, 0.0) / best if best else 0.0
    return weights


def cai_score(cds: str, usage: dict[str, float] | None = None) -> float | None:
    """Codon Adaptation Index (Sharp & Li 1987): geometric mean of w_i."""
    weights = relative_adaptiveness(usage)
    values: list[float] = []
    for codon in codons_of(cds):
        amino = DNA_CODON_TABLE.get(codon)
        if amino is None or amino in CAI_EXCLUDED_AMINO_ACIDS:
            continue
        weight = weights.get(codon)
        if weight is None or weight <= 0:
            continue
        values.append(math.log(weight))
    if not values:
        return None
    return math.exp(sum(values) / len(values))


def effective_number_of_codons(cds: str) -> float | None:
    """Wright's Nc (1990) with 6-fold families split into 2+4 subfamilies."""
    counts: dict[tuple[str, ...], dict[str, int]] = {family: {} for family in NC_SPLIT_FAMILIES}
    for codon in codons_of(cds):
        for family in NC_SPLIT_FAMILIES:
            if codon in family:
                counts[family][codon] = counts[family].get(codon, 0) + 1
                break
    group_f: dict[int, list[float]] = {2: [], 3: [], 4: []}
    for family, tally in counts.items():
        n = sum(tally.values())
        if n < 2:
            continue
        homozygosity = (n * sum((count / n) ** 2 for count in tally.values()) - 1) / (n - 1)
        group_f[len(family)].append(homozygosity)
    if not any(group_f[size] for size in (2, 3, 4)):
        return None
    nc = 2.0
    for size, family_count in ((2, 12), (3, 1), (4, 8)):
        values = group_f[size]
        if values:
            nc += family_count / (sum(values) / len(values))
    return nc


def codon_pair_score(cds: str, usage: dict[str, float] | None = None) -> float | None:
    """Mean smoothed log-odds of adjacent codon pairs against a usage null model.

    CPS(p) = ln((observed(p) + 0.5) / (expected(p) + 0.5)) with
    expected(p) = f(c1) * f(c2) * N_pairs under independent codon usage.
    """
    table = usage or HUMAN_CODON_USAGE
    codon_list = codons_of(cds)
    pairs = list(zip(codon_list, codon_list[1:], strict=False))
    if not pairs:
        return None
    observed: dict[tuple[str, str], int] = {}
    for pair in pairs:
        observed[pair] = observed.get(pair, 0) + 1
    total = sum(table.values())
    scores = [
        math.log(
            (count + 0.5)
            / (max((table.get(first, 0.0) / total) * (table.get(second, 0.0) / total) * len(pairs), 0.0) + 0.5)
        )
        for (first, second), count in observed.items()
    ]
    return sum(scores) / len(scores)


def motif_counts(sequence: str, motifs: list[str]) -> dict[str, int]:
    return {motif: sequence.count(motif) for motif in motifs}


def parse_motif_list(value: Any) -> list[str]:
    tokens = re.split(r"[\s,;]+", str(value or "").strip().upper())
    return [token for token in tokens if token]


def wrap_sequence(sequence: str, width: int) -> list[str]:
    return [sequence[offset:offset + width] for offset in range(0, len(sequence), width)]


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class CodonDesignNode(BaseNode):
    """Metadata shared by deterministic stdlib codon-design nodes."""

    CATEGORY = "codon_design"
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_EXECUTABLES: ClassVar[list[str]] = []
    REQUIRED_CONDA_PACKAGES: ClassVar[list[str]] = []
    VERSION = "1.0.0"
    ENVIRONMENT = {"python": "3.12", "stdlib_only": True}
    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / filename for filename in cls.OUTPUT_FILENAMES]

    @classmethod
    def node_output_path(cls, context: Any, filename: str) -> Path:
        base = Path(getattr(context, "node_dir", ".") if context else ".")
        output_dir = base / cls.NODE_ID
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / filename

    @staticmethod
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

    @staticmethod
    def validate_float(
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

    @staticmethod
    def validate_choice(value: Any, key: str, choices: tuple[str, ...]) -> bool | str:
        if str(value) not in choices:
            return f"Input '{key}' must be one of: {', '.join(choices)}"
        return True
