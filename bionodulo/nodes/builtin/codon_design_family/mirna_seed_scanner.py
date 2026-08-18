"""TargetScan-style miRNA seed scanner for 3'UTR sequences."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .adapter import (
    CodonDesignNode,
    read_fasta_records,
    reverse_complement_rna,
    to_rna,
    validate_sequence_literal,
    write_json,
    write_record_table,
)


RNA_ALPHABET = frozenset("ACGU")
SEED_LENGTH = 7
PER_RECORD_COLUMNS = ["id", "weighted_hits", "n_hits"]


def scan_seed_hits(target: str, seeds: list[dict[str, Any]], context_length: int) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for entry in seeds:
        seed = entry["seed"]
        match = reverse_complement_rna(seed)
        prefix_match = reverse_complement_rna(seed[:6])
        for offset in range(0, max(0, len(target) - SEED_LENGTH + 1)):
            full = target[offset:offset + SEED_LENGTH] == match
            with_anchor = offset > 0 and target[offset - 1] == "A"
            if full and with_anchor:
                seed_type = "8mer"
                start = offset - 1
                end = offset + SEED_LENGTH
            elif full:
                seed_type = "7mer-m8"
                start = offset
                end = offset + SEED_LENGTH
            elif with_anchor and target[offset:offset + 6] == prefix_match:
                seed_type = "7mer-A1"
                start = offset - 1
                end = offset + 6
            else:
                continue
            hits.append(
                {
                    "mirna_id": entry["mirna_id"],
                    "seed": seed,
                    "seed_type": seed_type,
                    "start": start + 1,
                    "end": end,
                    "site": target[start:end],
                    "context": target[max(0, start - context_length):min(len(target), end + context_length)],
                    "weight": entry["weight"],
                }
            )
    return hits


def parse_seed_file(path: Path) -> list[dict[str, Any]]:
    """Parse a TSV/CSV seed table with columns mirna_id, seed[, weight]."""
    text = path.read_text(encoding="utf-8")
    sample = text.splitlines()[0] if text.splitlines() else ""
    delimiter = "\t" if "\t" in sample else ","
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    fieldnames = reader.fieldnames or []
    lower = [name.strip().lower() for name in fieldnames]
    id_column = next((name for name, key in zip(fieldnames, lower) if key in {"mirna", "mirna_id", "id"}), None)
    seed_column = next((name for name, key in zip(fieldnames, lower) if key in {"seed", "site", "sequence"}), None)
    weight_column = next((name for name, key in zip(fieldnames, lower) if key in {"weight", "score"}), None)
    if id_column is None or seed_column is None:
        raise ValueError("Seed file must have header columns for miRNA id and seed")
    seeds: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in reader:
        mirna_id = str(row.get(id_column) or "").strip()
        seed = str(row.get(seed_column) or "").strip().upper().replace("T", "U")
        if not mirna_id or not seed:
            continue
        if len(seed) != SEED_LENGTH or set(seed) - RNA_ALPHABET:
            raise ValueError(f"Seed for '{mirna_id}' must be {SEED_LENGTH} ACGU characters: {seed}")
        if seed in seen:
            raise ValueError(f"Duplicate seed for '{mirna_id}': {seed}")
        seen.add(seed)
        weight = 1.0
        if weight_column is not None and str(row.get(weight_column) or "").strip():
            weight = float(str(row[weight_column]).strip())
        seeds.append({"mirna_id": mirna_id, "seed": seed, "weight": weight})
    if not seeds:
        raise ValueError("Seed file contains no usable rows")
    return seeds


class MiRNASeedScannerNode(CodonDesignNode):
    """Scan one target sequence for TargetScan-style miRNA seed matches."""

    NODE_ID = "mirna_seed_scanner"
    DISPLAY_NAME = "miRNA Seed Scanner"
    DESCRIPTION = (
        "Scan one mRNA/3'UTR sequence for 7mer-m8, 7mer-A1, and 8mer seed matches per TargetScan "
        "definitions, using a TSV/CSV seed table (miRNA id, 7nt seed, optional weight). Context+ "
        "scoring from the Agarwal et al. 2015 model is out of scope; weights are user-supplied."
    )
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "miRNA",
        "seed match",
        "3'UTR",
        "TargetScan",
        "7mer-m8",
        "7mer-A1",
        "8mer",
        "target prediction",
    ]
    RETURN_TYPES = ("TSV", "JSON", "TSV", "JSON")
    RETURN_NAMES = ("hits", "summary", "per_record", "per_record_json")
    OUTPUT_FILENAMES = ("mirna_seed_hits.tsv", "mirna_seed_summary.json", "per_record.tsv", "per_record.json")
    DOCUMENTATION_URL = "https://www.targetscan.org/"
    CITATION_DOIS = ["10.1016/j.molcel.2005.07.016", "10.1016/j.molcel.2015.06.018"]
    CITATION_URLS = [
        "https://doi.org/10.1016/j.molcel.2005.07.016",
        "https://doi.org/10.1016/j.molcel.2015.06.018",
    ]
    CITATION_TEXT = (
        "Conserved seed pairing, often flanked by adenosines, implies that over a third of human genes "
        "are microRNA targets; Predicting effective microRNA target sites in mammalian mRNAs."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "target": (
                    "STRING",
                    {"multiline": True, "default": "", "description": "mRNA/3'UTR sequence, or a path to a FASTA/plain file"},
                ),
                "seed_file": (
                    "FILE",
                    {"description": "TSV/CSV with columns miRNA id, 7nt seed, optional weight"},
                ),
            },
            "optional": {
                "context_length": ("INT", {"default": 10, "min": 0, "max": 100, "description": "Flanking nucleotides in the hits table"}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not str(inputs.get("target", "") or "").strip():
            return "Input 'target' must be a non-empty sequence or file path"
        validation = validate_sequence_literal(inputs.get("target"), "target", alphabet=set("ACGTUN"))
        if validation is not True:
            return validation
        seed_file = str(inputs.get("seed_file", "") or "").strip()
        if not seed_file:
            return "Input 'seed_file' must be a non-empty path"
        return cls.validate_int(inputs.get("context_length", 10), "context_length", minimum=0, maximum=100)

    async def run(self, **kwargs: Any) -> tuple[str, str, str, str]:
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        context = kwargs.get("context")
        records = read_fasta_records(kwargs.get("target"), "target")
        for _, raw_record in records:
            invalid = set(raw_record) - set("ACGTUN")
            if invalid:
                raise ValueError(f"Input 'target' contains non-RNA characters: {''.join(sorted(invalid))}")
        target = to_rna("".join(sequence for _, sequence in records))
        seeds = parse_seed_file(Path(str(kwargs["seed_file"])))
        context_length = int(kwargs.get("context_length", 10))

        hits = scan_seed_hits(target, seeds, context_length)

        per_record_rows: list[dict[str, Any]] = []
        for record_id, raw_record in records:
            record_hits = scan_seed_hits(to_rna(raw_record), seeds, context_length)
            per_record_rows.append(
                {
                    "id": record_id,
                    "weighted_hits": sum(float(hit["weight"]) for hit in record_hits),
                    "n_hits": len(record_hits),
                }
            )

        by_type: dict[str, int] = {}
        by_mirna: dict[str, int] = {}
        weighted_score = 0.0
        for hit in hits:
            by_type[hit["seed_type"]] = by_type.get(hit["seed_type"], 0) + 1
            by_mirna[hit["mirna_id"]] = by_mirna.get(hit["mirna_id"], 0) + 1
            weighted_score += float(hit["weight"])
        summary = {
            "target_length_nt": len(target),
            "seed_count": len(seeds),
            "hit_count": len(hits),
            "hits_by_type": by_type,
            "hits_by_mirna": by_mirna,
            "weighted_score": weighted_score,
            "context_length": context_length,
            "seed_definition": "7nt seed = miRNA nucleotides 2-8",
        }

        tsv_path = self.node_output_path(context, "mirna_seed_hits.tsv")
        header = ["mirna_id", "seed", "seed_type", "start", "end", "site", "context", "weight"]
        lines = ["\t".join(header)]
        for hit in sorted(hits, key=lambda hit: (hit["start"], hit["mirna_id"])):
            lines.append("\t".join(str(hit[column]) for column in header))
        tsv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        json_path = self.node_output_path(context, "mirna_seed_summary.json")
        write_json(json_path, summary)
        per_record_tsv = self.node_output_path(context, "per_record.tsv")
        write_record_table(per_record_tsv, PER_RECORD_COLUMNS, per_record_rows)
        per_record_json = self.node_output_path(context, "per_record.json")
        write_json(per_record_json, per_record_rows)
        return (str(tsv_path), str(json_path), str(per_record_tsv), str(per_record_json))
