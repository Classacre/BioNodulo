"""GRPO-inspired zeroth-order policy update over synonymous-codon logits."""

from __future__ import annotations

import math
from typing import Any

from .adapter import (
    AMINO_ACID_CODONS,
    CODON_AMINO_ACID,
    MLDesignNode,
    load_json_payload,
    load_json_mapping,
    node_output_dir,
    numeric_field,
    parse_candidates,
    validate_float_input,
    validate_int_input,
    write_json_file,
)

GRPO_URL = "https://arxiv.org/abs/2402.03300"
MO_GRPO_URL = "https://arxiv.org/abs/2605.01513"


class GroupRelativeOptimizerNode(MLDesignNode):
    """Apply one group-relative advantage update to the codon policy table."""

    NODE_ID = "group_relative_optimizer"
    DISPLAY_NAME = "Group Relative Optimizer"
    DESCRIPTION = (
        "GRPO-inspired zeroth-order update step: z-score group advantages "
        "A_i=(r_i-mean)/std over the candidate batch update a categorical "
        "codon policy table via advantage-weighted counts, with softmax temperature, "
        "learning-rate step, epsilon probability floor on every synonymous codon, and "
        "ref_strength mixing toward the reference table (the KL-to-reference analogue). "
        "Also selects the top-k elite set and emits the batch's best candidate. "
        "Empty-tolerant: an empty candidate batch and/or empty ranked list (zero "
        "elites, e.g. a first iteration where every evaluator produced no rows) emits "
        "the policy unchanged (pass-through of the wired policy_table, else an empty "
        "uniform skeleton), an empty elite set, and stats with n_candidates 0 and "
        "best_composite null instead of erroring; candidates absent from the ranked "
        "list are dropped rather than fatal."
    )
    SEARCH_ALIASES = [
        "GRPO",
        "group relative policy optimization",
        "reinforcement learning",
        "zeroth-order optimization",
        "elite selection",
        "advantage",
        "design loop",
        "MO-GRPO",
    ]
    RETURN_TYPES = ("JSON", "JSON", "JSON")
    RETURN_NAMES = ("policy_table", "elites", "best")
    CITATION_URLS = [GRPO_URL, MO_GRPO_URL]
    CITATION_TEXT = (
        "Group-relative advantage updates follow DeepSeekMath's GRPO; multi-objective "
        "codon-policy optimization for mRNA design follows the MO-GRPO antecedent."
    )
    DOCUMENTATION_URL = GRPO_URL

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "candidates": ("JSON", {"description": "Candidate batch JSON evaluated this iteration"}),
                "ranked": ("JSON", {"description": "Ranked composite JSON from multi_objective_scorer"}),
            },
            "optional": {
                "policy_table": ("JSON", {"default": "", "description": "Current codon policy table; uniform when absent"}),
                "previous_best_composite": ("FLOAT", {"default": None, "description": "Best composite before this batch; enables improvement_vs_prev"}),
                "top_k": ("INT", {"default": 8, "min": 1, "max": 1000}),
                "learning_rate": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0}),
                "temperature": ("FLOAT", {"default": 1.0, "min": 0.01, "max": 10.0}),
                "epsilon": ("FLOAT", {"default": 0.01, "min": 0.0001, "max": 0.5, "description": "Minimum probability kept on each synonymous codon"}),
                "ref_strength": ("FLOAT", {"default": 0.1, "min": 0.0, "max": 1.0, "description": "Mixing toward the reference policy table"}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_int_input(inputs.get("top_k", 8), "top_k", minimum=1, maximum=1000)
        if validation is not True:
            return validation
        for key, default, minimum, maximum in (
            ("learning_rate", 1.0, 0.0, 10.0),
            ("temperature", 1.0, 0.01, 10.0),
            ("epsilon", 0.01, 0.0001, 0.5),
            ("ref_strength", 0.1, 0.0, 1.0),
        ):
            validation = validate_float_input(
                inputs.get(key, default), key, minimum=minimum, maximum=maximum
            )
            if validation is not True:
                return validation
        return True

    async def run(self, **kwargs: Any) -> tuple[str, str, str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        candidates = parse_candidates(kwargs["candidates"], "candidates", allow_empty=True)
        composites = self._composites(kwargs["ranked"], candidates)
        # Tolerate partial coverage: the scorer may legitimately rank fewer ids
        # than the batch (some evaluators produced no rows for them).
        candidates = [entry for entry in candidates if entry["id"] in composites]
        if not candidates:
            return self._zero_elite_passthrough(kwargs, context)

        proteins = {self._protein(entry["cds"], entry["id"]) for entry in candidates}
        if len(proteins) != 1:
            raise ValueError("All candidates must encode one identical protein for codon-policy updates")

        values = [composites[entry["id"]] for entry in candidates]
        mean = sum(values) / len(values)
        std = math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))
        advantages = [0.0 if std == 0 else (value - mean) / std for value in values]

        top_k = min(int(kwargs.get("top_k", 8)), len(candidates))
        order = sorted(range(len(candidates)), key=lambda idx: (-values[idx], candidates[idx]["id"]))
        elite_indices = order[:top_k]
        elites = [
            {
                "id": candidates[idx]["id"],
                "cds": candidates[idx]["cds"],
                "utr5": candidates[idx]["utr5"],
                "utr3": candidates[idx]["utr3"],
                "composite": values[idx],
                "advantage": advantages[idx],
            }
            for idx in elite_indices
        ]
        best_index = elite_indices[0]
        best = dict(elites[0])

        reference = self._load_policy(kwargs.get("policy_table"), candidates)
        updated = self._update(
            candidates,
            advantages,
            reference,
            float(kwargs.get("learning_rate", 1.0)),
            float(kwargs.get("temperature", 1.0)),
            float(kwargs.get("epsilon", 0.01)),
            float(kwargs.get("ref_strength", 0.1)),
        )

        previous = kwargs.get("previous_best_composite")
        improvement = None
        if previous is not None:
            improvement = values[best_index] - float(previous)

        output_dir = node_output_dir(self, context)
        policy_path = output_dir / "policy_table.json"
        elites_path = output_dir / "elites.json"
        best_path = output_dir / "best.json"
        write_json_file(policy_path, updated)
        write_json_file(
            elites_path,
            {
                "elites": elites,
                "best": best,
                "stats": {
                    "n_candidates": len(candidates),
                    "mean": mean,
                    "std": std,
                    "best_composite": values[best_index],
                    "improvement_vs_prev": improvement,
                },
            },
        )
        write_json_file(best_path, best)
        return (str(policy_path), str(elites_path), str(best_path))

    def _zero_elite_passthrough(self, kwargs: dict[str, Any], context: Any) -> tuple[str, str, str]:
        """Zero elites (empty batch and/or empty ranked list): do not error.

        Emits the policy unchanged (the wired policy_table verbatim when one
        was supplied, else a canonical empty uniform skeleton that
        policy_sampler falls back to uniform sampling from) plus an empty
        elite set with best_composite null, so loop iteration one with an
        empty candidate batch survives without hidden state.
        """
        payload = load_json_mapping(kwargs.get("policy_table"), "policy_table")
        policy = (
            payload
            if isinstance(payload, dict)
            else {
                "format": "categorical_codon_policy_v1",
                "n_positions": 0,
                "position_key_style": "0-based codon index",
                "positions": {},
            }
        )
        output_dir = node_output_dir(self, context)
        policy_path = output_dir / "policy_table.json"
        elites_path = output_dir / "elites.json"
        best_path = output_dir / "best.json"
        write_json_file(policy_path, policy)
        write_json_file(
            elites_path,
            {
                "elites": [],
                "best": None,
                "stats": {
                    "n_candidates": 0,
                    "mean": None,
                    "std": None,
                    "best_composite": None,
                    "improvement_vs_prev": None,
                },
            },
        )
        write_json_file(best_path, None)
        return (str(policy_path), str(elites_path), str(best_path))

    @staticmethod
    def _composites(value: Any, candidates: list[dict[str, Any]]) -> dict[str, float]:
        """Map candidate id -> composite; ids absent from ranked are omitted.

        An empty ranked list yields {} (the zero-elite pass-through); entries
        in ranked that match no candidate are ignored. Structural errors in a
        present, non-empty payload remain fatal.
        """
        payload = load_json_payload(value, "ranked")
        if payload is None:
            raise ValueError("Input 'ranked' must be a non-empty JSON array from multi_objective_scorer")
        if not isinstance(payload, list):
            raise ValueError("Input 'ranked' must be a non-empty JSON array from multi_objective_scorer")
        composites: dict[str, float] = {}
        known = {entry["id"] for entry in candidates}
        for index, entry in enumerate(payload):
            if not isinstance(entry, dict):
                raise ValueError(f"Input 'ranked' entry {index} must be a JSON object")
            cid = str(entry.get("id", "")).strip()
            if not cid:
                raise ValueError(f"Input 'ranked' entry {index} is missing a non-empty 'id'")
            if known and cid not in known:
                continue
            composites[cid] = numeric_field(entry, "composite", f"Input 'ranked' entry {cid}")
        return composites

    @staticmethod
    def _protein(cds: str, identifier: str) -> str:
        amino_acids: list[str] = []
        for index in range(0, len(cds), 3):
            amino_acid = CODON_AMINO_ACID.get(cds[index : index + 3])
            if amino_acid is None:
                raise ValueError(f"Candidate {identifier} contains unknown codon at position {index // 3}")
            amino_acids.append(amino_acid)
        return "".join(amino_acids)

    @staticmethod
    def _synonym_domains(candidates: list[dict[str, Any]]) -> list[list[str]]:
        reference = candidates[0]["cds"]
        domains: list[list[str]] = []
        for position in range(len(reference) // 3):
            amino_acid = CODON_AMINO_ACID[reference[position * 3 : position * 3 + 3]]
            if amino_acid == "*":
                raise ValueError(f"Candidate CDS contains a stop codon at position {position}")
            domains.append(AMINO_ACID_CODONS[amino_acid])
        return domains

    def _load_policy(
        self,
        value: Any,
        candidates: list[dict[str, Any]],
    ) -> dict[str, dict[str, float]]:
        domains = self._synonym_domains(candidates)
        reference: dict[str, dict[str, float]] = {}
        for position, synonyms in enumerate(domains):
            reference[str(position)] = {codon: 1.0 / len(synonyms) for codon in synonyms}
        payload = load_json_mapping(value, "policy_table")
        if payload is None:
            return reference
        positions = payload.get("positions")
        if not isinstance(positions, dict):
            raise ValueError("Input 'policy_table' must contain a 'positions' object")
        if not positions:
            # The zero-elite pass-through skeleton (or any empty policy
            # table): nothing learned yet, so update from the uniform
            # reference rather than failing the recovery iteration.
            return reference
        n_positions = len(domains)
        supplied = {str(key) for key in positions}
        expected = {str(index) for index in range(n_positions)}
        if supplied != expected:
            raise ValueError(
                f"Input 'policy_table' positions must cover exactly {n_positions} position keys (0..{n_positions - 1})"
            )
        for position, synonyms in enumerate(domains):
            entry = positions[str(position)]
            if not isinstance(entry, dict) or set(entry) != set(synonyms):
                raise ValueError(
                    f"Input 'policy_table' position {position} must define exactly the synonymous codons: "
                    f"{', '.join(synonyms)}"
                )
            raw = [float(entry[codon]) for codon in synonyms]
            if any(weight < 0 for weight in raw) or sum(raw) <= 0:
                raise ValueError(f"Input 'policy_table' position {position} weights must be non-negative with a positive sum")
            total = sum(raw)
            reference[str(position)] = {codon: weight / total for codon, weight in zip(synonyms, raw, strict=True)}
        return reference

    def _update(
        self,
        candidates: list[dict[str, Any]],
        advantages: list[float],
        reference: dict[str, dict[str, float]],
        learning_rate: float,
        temperature: float,
        epsilon: float,
        ref_strength: float,
    ) -> dict[str, Any]:
        n_positions = len(candidates[0]["cds"]) // 3
        n_candidates = len(candidates)
        synonyms_by_position = [sorted(reference[str(position)]) for position in range(n_positions)]
        updated: dict[str, dict[str, float]] = {}
        for position in range(n_positions):
            synonyms = synonyms_by_position[position]
            reference_probs = reference[str(position)]
            counts = {codon: 0.0 for codon in synonyms}
            for entry, advantage in zip(candidates, advantages, strict=True):
                chosen = entry["cds"][position * 3 : position * 3 + 3]
                counts[chosen] = counts.get(chosen, 0.0) + advantage / n_candidates
            logits = {
                codon: math.log(max(reference_probs[codon], 1e-12)) + learning_rate * counts[codon]
                for codon in synonyms
            }
            probabilities = self._softmax([logits[codon] for codon in synonyms], temperature)
            mixed = [
                (1.0 - ref_strength) * probability + ref_strength * reference_probs[codon]
                for codon, probability in zip(synonyms, probabilities, strict=True)
            ]
            mixed = self._floor(mixed, epsilon)
            updated[str(position)] = dict(zip(synonyms, mixed, strict=True))
        return {
            "format": "categorical_codon_policy_v1",
            "n_positions": n_positions,
            "position_key_style": "0-based codon index",
            "positions": updated,
        }

    @staticmethod
    def _softmax(values: list[float], temperature: float) -> list[float]:
        top = max(values)
        exponentials = [math.exp((value - top) / temperature) for value in values]
        total = sum(exponentials)
        return [value / total for value in exponentials]

    @staticmethod
    def _floor(probabilities: list[float], epsilon: float) -> list[float]:
        floored = [max(value, epsilon) for value in probabilities]
        total = sum(floored)
        return [value / total for value in floored]
