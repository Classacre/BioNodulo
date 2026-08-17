"""Deterministic synonymous-codon candidate sampler for iterative mRNA design."""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from typing import Any

from .adapter import (
    AMINO_ACID_CODONS,
    CODON_AMINO_ACID,
    MLDesignNode,
    STRATEGIES,
    load_json_mapping,
    node_output_dir,
    read_sequence_text,
    translate,
    validate_choice_input,
    validate_int_input,
    write_fasta_file,
    write_json_file,
)


class CandidateGeneratorNode(MLDesignNode):
    """Generate a seeded batch of synonymous-codon mRNA candidates."""

    NODE_ID = "candidate_generator"
    DISPLAY_NAME = "Candidate Generator"
    DESCRIPTION = (
        "Generate N deterministic synonymous-codon variants of a base CDS "
        "(uniform, codon-weighted, or GC-target-biased sampling); the pi_old sampler "
        "of the iterative mRNA design loop."
    )
    SEARCH_ALIASES = [
        "mRNA design",
        "codon optimization",
        "synonymous codon",
        "candidate sampling",
        "design loop",
        "pi_old",
    ]
    RETURN_TYPES = ("JSON", "FASTA")
    RETURN_NAMES = ("candidates", "fasta")
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/random.html"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "base_cds": ("STRING", {"description": "Base CDS nucleotide sequence or FASTA file path"}),
            },
            "optional": {
                "utr5_template": ("STRING", {"default": "", "description": "Optional 5' UTR attached to every candidate"}),
                "utr3_template": ("STRING", {"default": "", "description": "Optional 3' UTR attached to every candidate"}),
                "codon_weights": ("JSON", {"default": "", "description": "codon -> positive weight JSON for synonymous_weighted"}),
                "n_candidates": ("INT", {"default": 24, "min": 1, "max": 1000}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 2147483647}),
                "strategy": ("STRING", {"default": "synonymous_uniform", "options": list(STRATEGIES)}),
                "gc_target": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "description": "GC fraction targeted by gc_jitter"}),
                "gc_sharpness": ("FLOAT", {"default": 10.0, "min": 0.1, "max": 100.0, "description": "GC-bias sharpness for gc_jitter"}),
                "id_prefix": ("STRING", {"default": "cand"}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not str(inputs.get("base_cds", "")).strip():
            return "Input 'base_cds' must be a non-empty sequence or file path"
        try:
            translate(read_sequence_text(inputs.get("base_cds"), "base_cds"), "base_cds")
        except ValueError as exc:
            return str(exc)
        validation = validate_choice_input(inputs.get("strategy", "synonymous_uniform"), "strategy", STRATEGIES)
        if validation is not True:
            return validation
        validation = validate_int_input(inputs.get("n_candidates", 24), "n_candidates", minimum=1, maximum=1000)
        if validation is not True:
            return validation
        validation = validate_int_input(inputs.get("seed", 0), "seed", minimum=0, maximum=2147483647)
        if validation is not True:
            return validation
        if str(inputs.get("strategy", "synonymous_uniform")) == "synonymous_weighted":
            weights = load_json_mapping(inputs.get("codon_weights"), "codon_weights")
            if weights is None:
                return "Input 'codon_weights' is required for strategy synonymous_weighted"
            for codon, weight in weights.items():
                if codon not in CODON_AMINO_ACID:
                    return f"Input 'codon_weights' contains unknown codon: {codon}"
                if isinstance(weight, bool) or not isinstance(weight, (int, float)) or float(weight) <= 0:
                    return f"Input 'codon_weights' weight for {codon} must be a positive number"
        return True

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        base_cds = read_sequence_text(kwargs["base_cds"], "base_cds")
        translate(base_cds, "base_cds")
        strategy = str(kwargs.get("strategy", "synonymous_uniform"))
        rng = random.Random(int(kwargs.get("seed", 0)))
        base_codons = [base_cds[index : index + 3] for index in range(0, len(base_cds), 3)]
        chooser = self._chooser(strategy, kwargs, rng)
        utr5 = read_sequence_text(kwargs.get("utr5_template", ""), "utr5_template")
        utr3 = read_sequence_text(kwargs.get("utr3_template", ""), "utr3_template")
        prefix = str(kwargs.get("id_prefix", "cand") or "cand").strip() or "cand"

        candidates: list[dict[str, Any]] = []
        for candidate_index in range(int(kwargs.get("n_candidates", 24))):
            codons = [chooser(position, codon) for position, codon in enumerate(base_codons)]
            candidates.append(
                {
                    "id": f"{prefix}_{candidate_index:04d}",
                    "cds": "".join(codons),
                    "utr5": utr5,
                    "utr3": utr3,
                }
            )

        output_dir = node_output_dir(self, context)
        json_path = output_dir / "candidates.json"
        fasta_path = output_dir / "candidates.fasta"
        write_json_file(json_path, candidates)
        write_fasta_file(
            fasta_path,
            [(entry["id"], f"{entry['utr5']}{entry['cds']}{entry['utr3']}") for entry in candidates],
        )
        return (str(json_path), str(fasta_path))

    def _chooser(self, strategy: str, kwargs: dict[str, Any], rng: random.Random) -> Callable[[int, str], str]:
        if strategy == "synonymous_weighted":
            return self._weighted_chooser(rng, load_json_mapping(kwargs.get("codon_weights"), "codon_weights"))
        if strategy == "gc_jitter":
            return self._gc_chooser(
                rng,
                float(kwargs.get("gc_target", 0.5)),
                float(kwargs.get("gc_sharpness", 10.0)),
            )
        return self._uniform_chooser(rng)

    @staticmethod
    def _synonyms(codon: str, position: int) -> list[str]:
        amino_acid = CODON_AMINO_ACID[codon]
        if amino_acid == "*":
            raise ValueError(f"Base CDS contains a stop codon at position {position}")
        return AMINO_ACID_CODONS[amino_acid]

    @classmethod
    def _uniform_chooser(cls, rng: random.Random) -> Callable[[int, str], str]:
        def choose(position: int, codon: str) -> str:
            synonyms = cls._synonyms(codon, position)
            if len(synonyms) == 1:
                return synonyms[0]
            return rng.choice(synonyms)

        return choose

    @classmethod
    def _weighted_chooser(
        cls,
        rng: random.Random,
        weights: dict[str, Any] | None,
    ) -> Callable[[int, str], str]:
        table = weights or {}

        def choose(position: int, codon: str) -> str:
            synonyms = cls._synonyms(codon, position)
            if len(synonyms) == 1:
                return synonyms[0]
            values = [max(float(table.get(synonym, 1.0)), 0.0) for synonym in synonyms]
            return rng.choices(synonyms, weights=values, k=1)[0]

        return choose

    @classmethod
    def _gc_chooser(cls, rng: random.Random, gc_target: float, sharpness: float) -> Callable[[int, str], str]:
        def choose(position: int, codon: str) -> str:
            synonyms = cls._synonyms(codon, position)
            if len(synonyms) == 1:
                return synonyms[0]
            weights = [
                math.exp(-sharpness * abs(sum(char in "GC" for char in synonym) / 3.0 - gc_target))
                for synonym in synonyms
            ]
            return rng.choices(synonyms, weights=weights, k=1)[0]

        return choose
