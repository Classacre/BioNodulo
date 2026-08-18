"""UTR feature-vector builder (no folding; length/GC/uORF/Kozak/AU/polyU)."""

from __future__ import annotations

import re
from typing import Any

from .adapter import (
    CodonDesignNode,
    gc_fraction,
    read_fasta_records,
    to_rna,
    validate_sequence_literal,
    write_json,
    write_record_table,
)


KOZAK_CONSENSUS_MINUS6_TO_MINUS1 = "GCCRCC"
STOP_CODONS_RNA = ("UAA", "UAG", "UGA")
PER_RECORD_COLUMNS = ["id", "kozak", "uorf_count", "gc", "length"]


def poly_u_runs(sequence: str, minimum: int) -> list[dict[str, int]]:
    runs: list[dict[str, int]] = []
    for match in re.finditer(r"U+", sequence):
        length = match.end() - match.start()
        if length >= minimum:
            runs.append({"start": match.start() + 1, "end": match.end(), "length": length})
    return runs


def count_uorfs(five_utr: str) -> int:
    """Count AUG triplets with an in-frame stop codon before the 3' end."""
    count = 0
    for offset in range(0, len(five_utr) - 2):
        if five_utr[offset:offset + 3] != "AUG":
            continue
        for stop_offset in range(offset + 3, len(five_utr) - 2, 3):
            if five_utr[stop_offset:stop_offset + 3] in STOP_CODONS_RNA:
                count += 1
                break
    return count


def kozak_features(five_utr: str) -> dict[str, Any]:
    """Score the -6..-1 positions preceding an assumed AUG start codon.

    The +4 position (G in GCCGCCAUGG) lies inside the CDS and cannot be
    evaluated from the UTR alone, so it is reported as unavailable.
    """
    context = five_utr[-6:]
    if len(context) < 6:
        context = "N" * (6 - len(context)) + context
    matches = sum(
        1
        for observed, consensus in zip(context, KOZAK_CONSENSUS_MINUS6_TO_MINUS1)
        if (consensus == "R" and observed in "AG") or (consensus != "R" and observed == consensus)
    )
    minus3 = context[3]
    return {
        "context_minus6_to_minus1": context,
        "consensus": KOZAK_CONSENSUS_MINUS6_TO_MINUS1 + "AUGG",
        "consensus_matches_minus6_to_minus1": matches,
        "minus3_purine": minus3 in "AG",
        "plus4_evaluated": False,
        "score_partial": round(matches / 6.0, 4),
    }


def utr_composition(sequence: str, poly_u_min: int) -> dict[str, Any]:
    runs = poly_u_runs(sequence, poly_u_min)
    au = sum(1 for base in sequence if base in "AU")
    return {
        "length_nt": len(sequence),
        "gc": gc_fraction(sequence),
        "au_fraction": (au / len(sequence)) if sequence else 0.0,
        "a_count": sequence.count("A"),
        "u_count": sequence.count("U"),
        "g_count": sequence.count("G"),
        "c_count": sequence.count("C"),
        "aug_count": len(re.findall(r"AUG", sequence)),
        "poly_u_min_length": poly_u_min,
        "poly_u_run_count": len(runs),
        "max_poly_u_length": max((run["length"] for run in runs), default=0),
        "poly_u_runs": runs,
    }


class UTRFeatureBuilderNode(CodonDesignNode):
    """Emit a folding-free 5'/3'UTR feature vector for mRNA design screens."""

    NODE_ID = "utr_feature_builder"
    DISPLAY_NAME = "UTR Feature Builder"
    DESCRIPTION = (
        "Compute folding-free UTR design features: length, GC, AU-richness, polyU stretches, uORF "
        "count (AUG with in-frame stop inside the 5'UTR), and a partial Kozak consensus score for the "
        "six nucleotides before an assumed AUG. Secondary-structure MFE is deliberately excluded; use "
        "the rnafold nodes for folding."
    )
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "UTR",
        "5'UTR",
        "3'UTR",
        "Kozak",
        "uORF",
        "polyU",
        "AU-rich",
        "translation efficiency",
        "mRNA design",
    ]
    RETURN_TYPES = ("JSON", "TSV", "JSON")
    RETURN_NAMES = ("features", "per_record", "per_record_json")
    OUTPUT_FILENAMES = ("utr_features.json", "per_record.tsv", "per_record.json")
    CITATION_DOIS = ["10.1016/0092-8674(86)90762-2"]
    CITATION_URLS = ["https://doi.org/10.1016/0092-8674(86)90762-2"]
    CITATION_TEXT = "Point mutations define a sequence flanking the AUG initiator codon that modulates translation."

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {},
            "optional": {
                "five_utr": (
                    "STRING",
                    {"multiline": True, "default": "", "description": "5'UTR sequence or file, ending immediately before the AUG"},
                ),
                "three_utr": (
                    "STRING",
                    {"multiline": True, "default": "", "description": "3'UTR sequence or file"},
                ),
                "poly_u_min": ("INT", {"default": 6, "min": 1, "max": 100, "description": "Minimum polyU run length reported"}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if inputs.get("five_utr", "") in (None, "") and inputs.get("three_utr", "") in (None, ""):
            return "Provide at least one of 'five_utr' or 'three_utr'"
        for key in ("five_utr", "three_utr"):
            if inputs.get(key, "") in (None, ""):
                continue
            validation = validate_sequence_literal(inputs.get(key), key, alphabet=set("ACGTUN"))
            if validation is not True:
                return validation
        return cls.validate_int(inputs.get("poly_u_min", 6), "poly_u_min", minimum=1, maximum=100)

    async def run(self, **kwargs: Any) -> tuple[str, str, str]:
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        context = kwargs.get("context")
        poly_u_min = int(kwargs.get("poly_u_min", 6))

        features: dict[str, Any] = {}
        five_records: list[tuple[str, str]] = []
        if str(kwargs.get("five_utr") or "").strip():
            five_records = read_fasta_records(kwargs.get("five_utr"), "five_utr")
            for _, raw_record in five_records:
                invalid = set(raw_record) - set("ACGTUN")
                if invalid:
                    raise ValueError(f"Input 'five_utr' contains non-RNA characters: {''.join(sorted(invalid))}")
            five_utr = to_rna("".join(sequence for _, sequence in five_records))
            features["five_utr"] = utr_composition(five_utr, poly_u_min)
            features["five_utr"]["uorf_count"] = count_uorfs(five_utr)
            features["kozak"] = kozak_features(five_utr)
        three_records: list[tuple[str, str]] = []
        if str(kwargs.get("three_utr") or "").strip():
            three_records = read_fasta_records(kwargs.get("three_utr"), "three_utr")
            for _, raw_record in three_records:
                invalid = set(raw_record) - set("ACGTUN")
                if invalid:
                    raise ValueError(f"Input 'three_utr' contains non-RNA characters: {''.join(sorted(invalid))}")
            three_utr = to_rna("".join(sequence for _, sequence in three_records))
            features["three_utr"] = utr_composition(three_utr, poly_u_min)
        features["mfe_note"] = "Secondary-structure MFE intentionally not computed; use the rnafold nodes."

        per_record_rows = [
            {
                "id": record_id,
                "kozak": kozak_features(to_rna(sequence))["score_partial"],
                "uorf_count": count_uorfs(to_rna(sequence)),
                "gc": gc_fraction(sequence),
                "length": len(sequence),
            }
            for record_id, sequence in (five_records or three_records)
        ]
        json_path = self.node_output_path(context, "utr_features.json")
        write_json(json_path, features)
        per_record_tsv = self.node_output_path(context, "per_record.tsv")
        write_record_table(per_record_tsv, PER_RECORD_COLUMNS, per_record_rows)
        per_record_json = self.node_output_path(context, "per_record.json")
        write_json(per_record_json, per_record_rows)
        return (str(json_path), str(per_record_tsv), str(per_record_json))
