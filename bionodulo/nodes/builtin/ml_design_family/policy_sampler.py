"""Sample the next candidate batch from an updated codon policy table."""

from __future__ import annotations

import random
from typing import Any

from .adapter import (
    AMINO_ACID_CODONS,
    MLDesignNode,
    load_json_mapping,
    node_output_dir,
    read_sequence_text,
    translate,
    validate_float_input,
    validate_int_input,
    write_fasta_file,
    write_json_file,
)


class PolicySamplerNode(MLDesignNode):
    """Draw the next candidate batch from categorical codon-policy probabilities."""

    NODE_ID = "policy_sampler"
    DISPLAY_NAME = "Policy Sampler"
    DESCRIPTION = (
        "Sample N candidate variants from a codon policy table (group_relative_optimizer "
        "output), applying temperature p^(1/T); with no policy table it falls back to "
        "uniform synonymous sampling. Output shape matches candidate_generator. "
        "n_candidates=0 emits an empty candidates JSON array and an empty FASTA instead "
        "of erroring, so downstream nodes receive an explicitly empty batch."
    )
    SEARCH_ALIASES = [
        "policy sampling",
        "categorical sampling",
        "codon policy",
        "mRNA design",
        "pi_new",
        "design loop",
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
                "policy_table": ("JSON", {"default": "", "description": "Policy table from group_relative_optimizer"}),
                "utr5_template": ("STRING", {"default": "", "description": "Optional 5' UTR attached to every candidate"}),
                "utr3_template": ("STRING", {"default": "", "description": "Optional 3' UTR attached to every candidate"}),
                "n_candidates": ("INT", {"default": 24, "min": 0, "max": 1000}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 2147483647}),
                "temperature": ("FLOAT", {"default": 1.0, "min": 0.01, "max": 10.0}),
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
        validation = validate_int_input(inputs.get("n_candidates", 24), "n_candidates", minimum=0, maximum=1000)
        if validation is not True:
            return validation
        validation = validate_int_input(inputs.get("seed", 0), "seed", minimum=0, maximum=2147483647)
        if validation is not True:
            return validation
        return validate_float_input(inputs.get("temperature", 1.0), "temperature", minimum=0.01, maximum=10.0)

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        base_cds = read_sequence_text(kwargs["base_cds"], "base_cds")
        protein = translate(base_cds, "base_cds")
        domains = [AMINO_ACID_CODONS[amino_acid] for amino_acid in protein]
        temperature = float(kwargs.get("temperature", 1.0))
        policy = self._policy(kwargs.get("policy_table"), domains, temperature)
        rng = random.Random(int(kwargs.get("seed", 0)))
        utr5 = read_sequence_text(kwargs.get("utr5_template", ""), "utr5_template")
        utr3 = read_sequence_text(kwargs.get("utr3_template", ""), "utr3_template")
        prefix = str(kwargs.get("id_prefix", "cand") or "cand").strip() or "cand"

        candidates: list[dict[str, Any]] = []
        for candidate_index in range(int(kwargs.get("n_candidates", 24))):
            codons = [rng.choices(domain, weights=policy[position], k=1)[0] for position, domain in enumerate(domains)]
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

    @staticmethod
    def _policy(value: Any, domains: list[list[str]], temperature: float) -> list[list[float]]:
        payload = load_json_mapping(value, "policy_table")
        positions = payload.get("positions") if payload else None
        if positions is not None and not isinstance(positions, dict):
            raise ValueError("Input 'policy_table' must contain a 'positions' object")
        weights: list[list[float]] = []
        for position, synonyms in enumerate(domains):
            if positions is None or str(position) not in positions:
                weights.append([1.0] * len(synonyms))
                continue
            entry = positions[str(position)]
            if not isinstance(entry, dict) or set(entry) != set(synonyms):
                raise ValueError(
                    f"Input 'policy_table' position {position} must define exactly the synonymous codons: "
                    f"{', '.join(synonyms)}"
                )
            raw = [float(entry[codon]) for codon in synonyms]
            if any(weight < 0 for weight in raw) or sum(raw) <= 0:
                raise ValueError(
                    f"Input 'policy_table' position {position} weights must be non-negative with a positive sum"
                )
            weights.append([weight ** (1.0 / temperature) for weight in raw])
        return weights
