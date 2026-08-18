"""Build the target x seed campaign matrix for design-loop sweeps."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import path_probe_is_file

from .adapter import (
    MLDesignNode,
    node_output_dir,
    validate_int_input,
    write_json_file,
    write_tsv_file,
)

DEFAULT_SEEDS = "13,101,2024,4242,9001"
DEFAULT_WEIGHTS = '{"cai":1.0,"structure":1.0,"gc":1.0,"immune":1.0,"mirna":1.0}'


class CampaignConfigBuilderNode(MLDesignNode):
    """Expand target CDS FASTAs x RNG seeds into the campaign pair table."""

    NODE_ID = "campaign_config_builder"
    DISPLAY_NAME = "Campaign Config Builder"
    DESCRIPTION = (
        "Builds the design-campaign matrix before a sweep: reads one CDS FASTA per "
        "target (lines like 'target_id<TAB>data/target.fasta', newline or semicolon "
        "separated; repo-relative paths resolve against the working directory) and "
        "emits the full target x seed cross-product as pairs.tsv (pair_id = "
        "'{target_id}__s{seed}', one uppercase cleaned CDS per row) plus a campaign "
        "config JSON (iterations, batch_size, top_k, evaluator weights, seeds, "
        "targets metadata) and the weights JSON for direct port wiring into "
        "multi_objective_scorer. All missing FASTA files are reported in one error."
    )
    SEARCH_ALIASES = [
        "campaign",
        "sweep",
        "seed matrix",
        "cross product",
        "design of experiments",
        "grid",
    ]
    RETURN_TYPES = ("TSV", "JSON", "JSON")
    RETURN_NAMES = ("pairs", "config", "weights")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "targets": (
                    "STRING",
                    {"multiline": True, "description": "One 'target_id<TAB>cds_fasta_path' per line; newline or semicolon separated"},
                ),
            },
            "optional": {
                "seeds": ("STRING", {"default": DEFAULT_SEEDS, "description": "Comma-separated integer RNG seeds"}),
                "iterations": ("INT", {"default": 30, "min": 1, "description": "Loop iterations per pair"}),
                "batch_size": ("INT", {"default": 48, "min": 1, "description": "Candidates sampled per iteration"}),
                "top_k": ("INT", {"default": 8, "min": 1, "description": "Elite count kept by the optimizer"}),
                "evaluator_weights": ("STRING", {"default": DEFAULT_WEIGHTS, "description": "JSON object mapping evaluator name to non-negative weight"}),
                "budget_usd": ("FLOAT", {"default": 50.0, "min": 0.0, "description": "Total compute budget marker for the campaign"}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for name, default in (("iterations", 30), ("batch_size", 48), ("top_k", 8)):
            check = validate_int_input(inputs.get(name, default), name, minimum=1)
            if check is not True:
                return check
        budget = inputs.get("budget_usd")
        if budget is not None:
            if isinstance(budget, bool) or not isinstance(budget, (int, float)) or not math.isfinite(float(budget)):
                return "Input 'budget_usd' must be a finite number"
            if float(budget) < 0:
                return "Input 'budget_usd' must be at least 0"
        return True

    async def run(self, **kwargs: Any) -> tuple[str, str, str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        targets = self._targets(kwargs["targets"])
        seeds = self._seeds(kwargs.get("seeds", DEFAULT_SEEDS))
        weights = self._weights(kwargs.get("evaluator_weights", DEFAULT_WEIGHTS))
        iterations = int(kwargs.get("iterations", 30))
        batch_size = int(kwargs.get("batch_size", 48))
        top_k = int(kwargs.get("top_k", 8))
        budget_usd = float(kwargs.get("budget_usd", 50.0))

        missing = [path for _, path in targets if not path_probe_is_file(path)]
        if missing:
            raise ValueError("Target FASTA files do not exist: " + ", ".join(missing))

        targets_meta: list[dict[str, Any]] = []
        sequences: dict[str, str] = {}
        for target_id, path_text in targets:
            text = Path(path_text).expanduser().read_text(encoding="utf-8")
            sequence = "".join(
                line.strip() for line in text.splitlines() if line.strip() and not line.startswith(">")
            ).upper()
            invalid = sorted({char for char in sequence if char not in "ACGT"})
            if invalid:
                raise ValueError(f"Target '{target_id}' FASTA contains non-ACGT character(s): {', '.join(invalid)}")
            if len(sequence) % 3 != 0:
                raise ValueError(f"Target '{target_id}' CDS length must be a multiple of three (got {len(sequence)})")
            sequences[target_id] = sequence
            gc = sum(char in "GC" for char in sequence) / len(sequence) if sequence else 0.0
            targets_meta.append(
                {
                    "target_id": target_id,
                    "path": path_text,
                    "n_codons": len(sequence) // 3,
                    "gc": gc,
                }
            )

        rows = [
            {
                "pair_id": f"{target_id}__s{seed}",
                "target_id": target_id,
                "seed": seed,
                "cds_sequence": sequences[target_id],
            }
            for target_id, _ in targets
            for seed in seeds
        ]
        config = {
            "n_pairs": len(rows),
            "iterations": iterations,
            "batch_size": batch_size,
            "top_k": top_k,
            "weights": weights,
            "seeds": seeds,
            "targets_meta": targets_meta,
            "budget_usd": budget_usd,
        }

        output_dir = node_output_dir(self, context)
        pairs_path = output_dir / "pairs.tsv"
        config_path = output_dir / "campaign_config.json"
        weights_path = output_dir / "weights.json"
        write_tsv_file(pairs_path, ["pair_id", "target_id", "seed", "cds_sequence"], rows)
        write_json_file(config_path, config)
        write_json_file(weights_path, weights)
        return (str(pairs_path), str(config_path), str(weights_path))

    @staticmethod
    def _targets(value: Any) -> list[tuple[str, str]]:
        text = str(value or "")
        lines: list[str] = []
        for chunk in text.replace(";", "\n").splitlines():
            chunk = chunk.strip()
            if chunk:
                lines.append(chunk)
        if not lines:
            raise ValueError("Input 'targets' must contain at least one 'target_id<TAB>cds_fasta_path' line")
        targets: list[tuple[str, str]] = []
        seen: set[str] = set()
        for index, line in enumerate(lines):
            fields = line.split("\t") if "\t" in line else line.split(None, 1)
            if len(fields) != 2 or not fields[0].strip() or not fields[1].strip():
                raise ValueError(f"Input 'targets' line {index + 1} must be 'target_id<TAB>cds_fasta_path' (got: {line!r})")
            target_id, path_text = fields[0].strip(), fields[1].strip()
            if target_id in seen:
                raise ValueError(f"Input 'targets' contains duplicate target_id: {target_id}")
            seen.add(target_id)
            targets.append((target_id, path_text))
        return targets

    @staticmethod
    def _seeds(value: Any) -> list[int]:
        text = str(value if value not in (None, "") else DEFAULT_SEEDS).strip()
        try:
            seeds = [int(part.strip()) for part in text.split(",") if part.strip()]
        except ValueError as exc:
            raise ValueError(f"Input 'seeds' must be a comma-separated integer list (got: {text!r})") from exc
        if not seeds:
            raise ValueError("Input 'seeds' must contain at least one integer")
        return seeds

    @staticmethod
    def _weights(value: Any) -> dict[str, float]:
        text = str(value if value not in (None, "") else DEFAULT_WEIGHTS).strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Input 'evaluator_weights' must be a JSON object of name->weight ({exc})") from exc
        if not isinstance(payload, dict) or not payload:
            raise ValueError("Input 'evaluator_weights' must be a non-empty JSON object of name->weight")
        weights: dict[str, float] = {}
        for name, weight in payload.items():
            if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(float(weight)):
                raise ValueError(f"Input 'evaluator_weights' weight for '{name}' must be a finite number")
            if float(weight) < 0:
                raise ValueError(f"Input 'evaluator_weights' weight for '{name}' must be non-negative")
            weights[str(name)] = float(weight)
        if sum(weights.values()) <= 0:
            raise ValueError("Input 'evaluator_weights' weights must sum to a positive total")
        return weights
