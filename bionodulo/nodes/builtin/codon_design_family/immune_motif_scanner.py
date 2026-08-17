"""Innate-immune motif scanner for RNA sequences."""

from __future__ import annotations

import re
from typing import Any

from .adapter import (
    CodonDesignNode,
    validate_sequence_literal,
    read_sequence_input,
    to_dna,
    to_rna,
    write_json,
)


DEFAULT_AU_WEIGHTS = "AUUA:1.0,UUUA:0.8,AUUU:0.6,UUUU:1.0,UAUU:0.5"
DEFAULT_TLR7_8_MOTIFS = "GUCCUUCAACU,UGUGUU,GUUGUU"
DEFAULT_TLR9_CPG_MOTIFS = "GTCGTT,AACGTT"
RNA_ALPHABET = frozenset("ACGU")


def parse_weighted_motifs(value: str) -> dict[str, float]:
    weights: dict[str, float] = {}
    for token in re.split(r"[\s,;]+", str(value or "").strip().upper()):
        if not token:
            continue
        motif, separator, weight = token.partition(":")
        if not separator:
            weight = "1.0"
        weights[motif] = float(weight)
    return weights


def scan_runs(sequence: str, base: str, minimum: int) -> list[dict[str, int]]:
    runs: list[dict[str, int]] = []
    for match in re.finditer(rf"{base}+", sequence):
        length = match.end() - match.start()
        if length >= minimum:
            runs.append({"start": match.start() + 1, "end": match.end(), "length": length})
    return runs


def scan_motif(sequence: str, motif: str) -> list[dict[str, int]]:
    return [
        {"start": match.start() + 1, "end": match.end()}
        for match in re.finditer(re.escape(motif), sequence)
    ]


class ImmuneMotifScannerNode(CodonDesignNode):
    """Scan RNA for U-rich, AU-rich, CpG, and TLR-agonist motifs."""

    NODE_ID = "immune_motif_scanner"
    DISPLAY_NAME = "Immune Motif Scanner"
    DESCRIPTION = (
        "Scan one RNA (or DNA) sequence for innate-immune stimulatory features: U-rich runs, weighted "
        "AU-rich 4-mers, CpG dinucleotides, TLR7/8-agonist GU/U-rich motifs (defaults from Heil et al. "
        "2004 RNA40-derived and GU-rich repeat agonists), and TLR9 CpG motifs (GTCGTT/AACGTT). "
        "U-content suppression of TLR recognition per Kariko et al. 2005. The summary score is a "
        "heuristic per-1000-nt aggregation, not a predictor of activation."
    )
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "innate immunity",
        "TLR7",
        "TLR8",
        "TLR9",
        "U-rich",
        "AU-rich element",
        "CpG",
        "immunogenicity",
        "mRNA design",
    ]
    RETURN_TYPES = ("JSON", "TSV")
    RETURN_NAMES = ("summary", "positions")
    OUTPUT_FILENAMES = ("immune_motifs.json", "immune_motifs.tsv")
    CITATION_DOIS = ["10.1016/j.immuni.2005.06.015", "10.1126/science.1093620"]
    CITATION_URLS = [
        "https://doi.org/10.1016/j.immuni.2005.06.015",
        "https://doi.org/10.1126/science.1093620",
    ]
    CITATION_TEXT = (
        "Suppression of RNA recognition by Toll-like receptors and the impact of nucleoside "
        "modification; species-specific recognition of single-stranded RNA via Toll-like receptor 7 and 8."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sequence": (
                    "STRING",
                    {"multiline": True, "default": "", "description": "RNA/DNA sequence, or a path to a FASTA/plain file"},
                ),
            },
            "optional": {
                "u_run_threshold": ("INT", {"default": 4, "min": 1, "max": 50, "description": "Minimum U-run length reported"}),
                "au_rich_weights": (
                    "STRING",
                    {"default": DEFAULT_AU_WEIGHTS, "description": "Weighted AU-rich 4-mers as MOTIF:WEIGHT pairs"},
                ),
                "tlr7_8_motifs": ("STRING", {"default": DEFAULT_TLR7_8_MOTIFS, "description": "TLR7/8-agonist GU/U-rich motifs"}),
                "tlr9_cpg_motifs": ("STRING", {"default": DEFAULT_TLR9_CPG_MOTIFS, "description": "TLR9 CpG motifs"}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not str(inputs.get("sequence", "") or "").strip():
            return "Input 'sequence' must be a non-empty sequence or file path"
        validation = validate_sequence_literal(inputs.get("sequence"), "sequence", alphabet=set("ACGTUN"))
        if validation is not True:
            return validation
        validation = cls.validate_int(inputs.get("u_run_threshold", 4), "u_run_threshold", minimum=1, maximum=50)
        if validation is not True:
            return validation
        weights: dict[str, dict[str, float]] = {}
        for key in ("au_rich_weights", "tlr7_8_motifs", "tlr9_cpg_motifs"):
            try:
                weights[key] = parse_weighted_motifs(str(inputs.get(key) or ""))
            except ValueError:
                return f"Input '{key}' must be MOTIF:WEIGHT or MOTIF entries"
        for key, allowed in (("au_rich_weights", "ACGU"), ("tlr7_8_motifs", "ACGU"), ("tlr9_cpg_motifs", "ACGT")):
            for motif in weights[key]:
                if set(motif) - set(allowed):
                    return f"Input '{key}' motifs must use {allowed} characters: {motif}"
        return True

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        context = kwargs.get("context")
        raw = read_sequence_input(kwargs.get("sequence"), "sequence")
        invalid = set(raw) - set("ACGTUN")
        if invalid:
            raise ValueError(
                f"Input 'sequence' contains non-RNA characters: {''.join(sorted(invalid))}"
            )
        rna = to_rna(raw)
        dna = to_dna(raw)
        u_threshold = int(kwargs.get("u_run_threshold", 4))
        au_weights = parse_weighted_motifs(
            str(kwargs.get("au_rich_weights") if kwargs.get("au_rich_weights") is not None else DEFAULT_AU_WEIGHTS)
        )
        tlr78_motifs = list(
            parse_weighted_motifs(
                str(kwargs.get("tlr7_8_motifs") if kwargs.get("tlr7_8_motifs") is not None else DEFAULT_TLR7_8_MOTIFS)
            )
        )
        tlr9_motifs = list(
            parse_weighted_motifs(
                str(kwargs.get("tlr9_cpg_motifs") if kwargs.get("tlr9_cpg_motifs") is not None else DEFAULT_TLR9_CPG_MOTIFS)
            )
        )
        for label, motifs in (("au_rich_weights", list(au_weights)), ("tlr7_8_motifs", tlr78_motifs)):
            for motif in motifs:
                if set(motif) - RNA_ALPHABET:
                    raise ValueError(f"Input '{label}' motifs must use ACGU characters: {motif}")
        for motif in tlr9_motifs:
            if set(motif) - set("ACGT"):
                raise ValueError(f"Input 'tlr9_cpg_motifs' motifs must use ACGT characters: {motif}")

        rows: list[tuple[str, str, int, int]] = []
        u_runs = scan_runs(rna, "U", u_threshold)
        for run in u_runs:
            rows.append(("u_run", "U" * run["length"], run["start"], run["end"]))
        au_hits = {motif: scan_motif(rna, motif) for motif in au_weights}
        au_counts = {motif: len(hits) for motif, hits in au_hits.items()}
        for motif, hits in au_hits.items():
            for hit in hits:
                rows.append(("au_rich_4mer", motif, hit["start"], hit["end"]))
        cpg_hits = scan_motif(dna, "CG")
        for hit in cpg_hits:
            rows.append(("cpg_dinucleotide", "CG", hit["start"], hit["end"]))
        tlr78_hits = {motif: scan_motif(rna, motif) for motif in tlr78_motifs}
        for motif, hits in tlr78_hits.items():
            for hit in hits:
                rows.append(("tlr7_8_motif", motif, hit["start"], hit["end"]))
        tlr9_hits = {motif: scan_motif(dna, motif) for motif in tlr9_motifs}
        for motif, hits in tlr9_hits.items():
            for hit in hits:
                rows.append(("tlr9_cpg_motif", motif, hit["start"], hit["end"]))

        au_weighted = sum(weight * au_counts[motif] for motif, weight in au_weights.items())

        def per_kb(count: float) -> float:
            return count * 1000 / len(rna) if rna else 0.0

        summary = {
            "length_nt": len(rna),
            "u_run_threshold": u_threshold,
            "u_run_count": len(u_runs),
            "u_runs_per_kb": per_kb(len(u_runs)),
            "max_u_run_length": max((run["length"] for run in u_runs), default=0),
            "u_fraction": (rna.count("U") / len(rna)) if rna else 0.0,
            "au_rich_4mer_counts": au_counts,
            "au_rich_weighted_score": au_weighted,
            "au_rich_weighted_per_kb": per_kb(au_weighted),
            "cpg_dinucleotide_count": len(cpg_hits),
            "cpg_per_kb": per_kb(len(cpg_hits)),
            "tlr7_8_motif_counts": {motif: len(hits) for motif, hits in tlr78_hits.items()},
            "tlr9_cpg_motif_counts": {motif: len(hits) for motif, hits in tlr9_hits.items()},
            "motif_hit_total": len(rows),
            "summary_score_heuristic": per_kb(
                len(u_runs) + au_weighted + len(cpg_hits) + sum(len(hits) for hits in tlr78_hits.values())
            ),
        }

        json_path = self.node_output_path(context, "immune_motifs.json")
        write_json(json_path, summary)
        tsv_path = self.node_output_path(context, "immune_motifs.tsv")
        lines = ["feature\tmotif\tstart\tend"]
        lines.extend(f"{feature}\t{motif}\t{start}\t{end}" for feature, motif, start, end in sorted(rows, key=lambda row: row[2]))
        tsv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return (str(json_path), str(tsv_path))
