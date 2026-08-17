"""Deterministic synonymous codon optimization node."""

from __future__ import annotations

from typing import Any

from .adapter import (
    AMINO_ACID_SYNONYMS,
    CODON_USAGE_SOURCE,
    HUMAN_CODON_USAGE,
    DNA_ALPHABET,
    DNA_CODON_TABLE,
    CodonDesignNode,
    cai_score,
    codons_of,
    gc_by_codon_position,
    gc_fraction,
    motif_counts,
    parse_motif_list,
    read_sequence_input,
    require_dna_cds,
    to_rna,
    translate_cds,
    validate_sequence_literal,
    wrap_sequence,
    write_json,
)


STRATEGIES = ("uniform", "gc_target", "cai_max", "balanced")
ORGANISMS = ("human",)
FASTA_LINE_WIDTH = 60


class CodonOptimizerNode(CodonDesignNode):
    """Recode one CDS with deterministic synonymous codon choices."""

    NODE_ID = "codon_optimizer"
    DISPLAY_NAME = "Codon Optimizer"
    DESCRIPTION = (
        "Deterministically recode a CDS using synonymous codons under uniform, CAI-maximizing, "
        "GC-targeting, or balanced strategies with forbidden-motif and repeat avoidance. "
        f"Usage table: {CODON_USAGE_SOURCE}. Heuristic synonymous recoding inspired by the "
        "LinearDesign dynamic-programming antecedent, which this node does not reproduce."
    )
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "codon optimization",
        "synonymous recoding",
        "CAI",
        "GC content",
        "mRNA design",
        "LinearDesign",
        "vaccine design",
    ]
    RETURN_TYPES = ("FASTA", "JSON")
    RETURN_NAMES = ("optimized_cds", "metrics")
    OUTPUT_FILENAMES = ("optimized_cds.fasta", "metrics.json")
    DOCUMENTATION_URL = "https://www.nature.com/articles/s41586-023-06127-z"
    CITATION_DOIS = ["10.1038/s41586-023-06127-z", "10.1093/nar/28.1.292"]
    CITATION_URLS = ["https://doi.org/10.1038/s41586-023-06127-z", "https://doi.org/10.1093/nar/28.1.292"]
    CITATION_TEXT = (
        "Algorithm for optimized mRNA design improves stability and immunogenicity; codon usage "
        "tabulated from international DNA sequence databases."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "cds": (
                    "STRING",
                    {"multiline": True, "default": "", "description": "CDS sequence, or a path to a FASTA/plain CDS file"},
                ),
            },
            "optional": {
                "organism": (list(ORGANISMS), {"default": "human"}),
                "strategy": (list(STRATEGIES), {"default": "balanced"}),
                "gc_target": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0}),
                "forbidden_motifs": (
                    "STRING",
                    {"default": "", "multiline": True, "description": "Comma/space separated DNA or RNA motifs to avoid"},
                ),
                "avoid_repeats": ("INT", {"default": 0, "min": 0, "max": 1000, "description": "Repeat-window length to de-duplicate; 0 disables"}),
                "output_alphabet": (["dna", "rna"], {"default": "dna"}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not str(inputs.get("cds", "") or "").strip():
            return "Input 'cds' must be a non-empty sequence or file path"
        validation = validate_sequence_literal(
            inputs.get("cds"), "cds", alphabet=DNA_ALPHABET, divisible_by_3=True
        )
        if validation is not True:
            return validation
        validation = cls.validate_choice(inputs.get("organism", "human"), "organism", ORGANISMS)
        if validation is not True:
            return validation
        validation = cls.validate_choice(inputs.get("strategy", "balanced"), "strategy", STRATEGIES)
        if validation is not True:
            return validation
        validation = cls.validate_float(inputs.get("gc_target", 0.5), "gc_target", minimum=0.0, maximum=1.0)
        if validation is not True:
            return validation
        validation = cls.validate_int(inputs.get("avoid_repeats", 0), "avoid_repeats", minimum=0, maximum=1000)
        if validation is not True:
            return validation
        for motif in parse_motif_list(inputs.get("forbidden_motifs", "")):
            if len(motif) < 2 or set(motif) - set("ACGTU"):
                return f"Input 'forbidden_motifs' entries must be ACGTU strings of length >= 2: {motif}"
        return cls.validate_choice(inputs.get("output_alphabet", "dna"), "output_alphabet", ("dna", "rna"))

    @classmethod
    def plan_codon(
        cls,
        amino: str,
        state: dict[str, Any],
        *,
        strategy: str,
        gc_target: float,
        forbidden: list[str],
        repeat_window: int,
    ) -> str:
        synonyms = AMINO_ACID_SYNONYMS[amino]
        eligible = [
            codon
            for codon in synonyms
            if not cls.violates_constraints(codon, state, forbidden=forbidden, repeat_window=repeat_window)
        ]
        if not eligible:
            state["constraint_escapes"] += 1
            eligible = list(synonyms)
        if strategy == "uniform":
            index = state["cycles"].get(amino, 0)
            state["cycles"][amino] = index + 1
            return eligible[index % len(eligible)]
        if strategy == "cai_max":
            return min(eligible, key=lambda codon: (-HUMAN_CODON_USAGE.get(codon, 0.0), codon))
        gc_state = gc_fraction(state["cds"])
        length = len(state["cds"])
        if strategy == "gc_target":
            return min(
                eligible,
                key=lambda codon: (
                    abs((gc_state * length + codon.count("G") + codon.count("C")) / (length + 3) - gc_target),
                    -HUMAN_CODON_USAGE.get(codon, 0.0),
                    codon,
                ),
            )
        return max(
            eligible,
            key=lambda codon: (
                0.7 * HUMAN_CODON_USAGE.get(codon, 0.0)
                + 0.3 * (1.0 - abs((codon.count("G") + codon.count("C")) / 3.0 - gc_target)),
                codon,
            ),
        )

    @staticmethod
    def violates_constraints(
        candidate: str,
        state: dict[str, Any],
        *,
        forbidden: list[str],
        repeat_window: int,
    ) -> bool:
        cds = state["cds"]
        extended = cds + candidate
        for motif in forbidden:
            if motif in extended or to_rna(motif) in to_rna(extended):
                return True
        if repeat_window >= 2 and len(extended) >= repeat_window:
            limit = len(extended) - repeat_window
            for offset in range(max(0, limit - 2), limit + 1):
                window = extended[offset:offset + repeat_window]
                occurrences = sum(
                    1
                    for other in range(0, limit + 1)
                    if extended[other:other + repeat_window] == window
                )
                if occurrences > 1:
                    return True
        return False

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        context = kwargs.get("context")
        original = require_dna_cds(read_sequence_input(kwargs.get("cds"), "cds"), "cds")
        strategy = str(kwargs.get("strategy", "balanced"))
        gc_target = float(kwargs.get("gc_target", 0.5))
        forbidden = [motif.replace("U", "T") for motif in parse_motif_list(kwargs.get("forbidden_motifs", ""))]
        repeat_window = int(kwargs.get("avoid_repeats", 0))
        output_alphabet = str(kwargs.get("output_alphabet", "dna"))

        state: dict[str, Any] = {"cds": "", "cycles": {}, "constraint_escapes": 0}
        for codon in codons_of(original):
            amino = DNA_CODON_TABLE.get(codon)
            if amino is None:
                raise ValueError(f"Input 'cds' contains invalid codon {codon}")
            if amino == "*":
                chosen = codon
            else:
                chosen = self.plan_codon(
                    amino,
                    state,
                    strategy=strategy,
                    gc_target=gc_target,
                    forbidden=forbidden,
                    repeat_window=repeat_window,
                )
            state["cds"] += chosen

        optimized = state["cds"]
        protein_original = translate_cds(original)
        protein_optimized = translate_cds(optimized)
        if protein_original != protein_optimized:
            raise ValueError("Codon optimization changed the encoded protein; refusing to emit")

        metrics = {
            "strategy": strategy,
            "organism_table": "human",
            "usage_source": CODON_USAGE_SOURCE,
            "length_nt": len(original),
            "length_codons": len(codons_of(original)),
            "protein_length": len(protein_original) - (1 if protein_original.endswith("*") else 0),
            "cai_before": cai_score(original),
            "cai_after": cai_score(optimized),
            "gc_before": gc_fraction(original),
            "gc_after": gc_fraction(optimized),
            "gc3_before": gc_by_codon_position(original).get("3"),
            "gc3_after": gc_by_codon_position(optimized).get("3"),
            "forbidden_motifs": forbidden,
            "motif_counts_before": motif_counts(original, forbidden),
            "motif_counts_after": motif_counts(optimized, forbidden),
            "repeat_window": repeat_window,
            "constraint_escapes": state["constraint_escapes"],
            "output_alphabet": output_alphabet,
        }

        emit = to_rna(optimized) if output_alphabet == "rna" else optimized
        fasta_path = self.node_output_path(context, "optimized_cds.fasta")
        lines = [">optimized_cds"]
        lines.extend(wrap_sequence(emit, FASTA_LINE_WIDTH))
        fasta_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        metrics_path = self.node_output_path(context, "metrics.json")
        write_json(metrics_path, metrics)
        return (str(fasta_path), str(metrics_path))
