"""Build the target x seed campaign matrix for design-loop sweeps."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import path_probe_is_file

from .adapter import (
    MLDesignNode,
    node_output_dir,
    validate_int_input,
    write_json_file,
    write_jsonl_file,
    write_tsv_file,
)

DEFAULT_SEEDS = "13,101,2024,4242,9001"
DEFAULT_WEIGHTS = '{"cai":1.0,"structure":1.0,"gc":1.0,"immune":1.0,"mirna":1.0}'
DEFAULT_OBJECTIVE_PORTS = (
    '{"cai":"scores_1","structure":"scores_2","gc":"scores_3","immune":"scores_4",'
    '"mirna":"scores_5","learned":"scores_6"}'
)


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
        "multi_objective_scorer. Loop-friendly JSONL siblings are emitted alongside: "
        "pairs.jsonl and targets.jsonl carry one JSON object per line (pair_id, "
        "target_id, seed, cds_sequence, weights_json, model_path) so foreach loops "
        "can iterate rows as self-describing strings, and ablations.jsonl carries one "
        "weight-ablation variant per line (ablation, evaluator_weights) when "
        "ablation_weights is provided. weights_json is port-keyed for "
        "multi_objective_scorer via the objective_ports mapping; annotate_key/"
        "annotate_value stamp one extra runtime column (e.g. a trained-model path) "
        "into every JSONL row. All missing FASTA files are reported in one error."
    )
    SEARCH_ALIASES = [
        "campaign",
        "sweep",
        "seed matrix",
        "cross product",
        "design of experiments",
        "grid",
    ]
    RETURN_TYPES = ("TSV", "JSONL", "JSONL", "JSON", "JSON", "JSONL")
    RETURN_NAMES = ("pairs", "pairs_jsonl", "targets_jsonl", "config", "weights", "ablations_jsonl")

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
                "objective_ports": (
                    "STRING",
                    {"default": DEFAULT_OBJECTIVE_PORTS, "multiline": True, "description": "JSON mapping evaluator name -> multi_objective_scorer scores_N port"},
                ),
                "ablation_weights": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "description": "One weight ablation per line: 'name<TAB>{\"evaluator\":0.0, ...}' merged onto the default weights",
                    },
                ),
                "annotate_key": ("STRING", {"default": "", "description": "Extra JSONL column name for annotate_value (e.g. model_path)"}),
                "annotate_value": ("STRING", {"default": "", "description": "Value stamped into every JSONL row under annotate_key; wire from a runtime artifact"}),
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
        ports_check = cls._objective_ports(inputs.get("objective_ports", DEFAULT_OBJECTIVE_PORTS))
        if isinstance(ports_check, str):
            return ports_check
        if str(inputs.get("annotate_key", "") or "").strip() and not str(inputs.get("annotate_value", "") or "").strip():
            return "Input 'annotate_value' must be non-empty when annotate_key is set"
        if str(inputs.get("annotate_value", "") or "").strip() and not str(inputs.get("annotate_key", "") or "").strip():
            return "Input 'annotate_key' must be non-empty when annotate_value is provided"
        return True

    async def run(self, **kwargs: Any) -> tuple[str, str, str, str, str, str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        targets = self._targets(kwargs["targets"])
        seeds = self._seeds(kwargs.get("seeds", DEFAULT_SEEDS))
        weights = self._weights(kwargs.get("evaluator_weights", DEFAULT_WEIGHTS))
        objective_ports = self._objective_ports(kwargs.get("objective_ports", DEFAULT_OBJECTIVE_PORTS))
        iterations = int(kwargs.get("iterations", 30))
        batch_size = int(kwargs.get("batch_size", 48))
        top_k = int(kwargs.get("top_k", 8))
        budget_usd = float(kwargs.get("budget_usd", 50.0))
        annotate_key = str(kwargs.get("annotate_key", "") or "").strip()
        annotate_value = str(kwargs.get("annotate_value", "") or "")
        port_weights = self._port_weights(weights, objective_ports)
        ablations = self._ablations(kwargs.get("ablation_weights", ""), weights)

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
            stop_codons = ("TAA", "TAG", "TGA")
            while len(sequence) >= 3 and sequence[-3:] in stop_codons:
                sequence = sequence[:-3]
            if not sequence:
                raise ValueError(f"Target '{target_id}' CDS is empty after stripping terminal stop codons")
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

        def jsonl_row(base: dict[str, Any]) -> dict[str, Any]:
            row = dict(base)
            row["weights_json"] = json.dumps(port_weights, sort_keys=True)
            row["model_path"] = annotate_value if annotate_key == "model_path" else ""
            if annotate_key and annotate_key != "model_path":
                row[annotate_key] = annotate_value
            return row

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
        jsonl_rows = [
            jsonl_row(
                {
                    "pair_id": row["pair_id"],
                    "target_id": row["target_id"],
                    "seed": row["seed"],
                    "cds_sequence": row["cds_sequence"],
                }
            )
            for row in rows
        ]
        targets_rows = [
            jsonl_row({"target_id": target_id, "cds_sequence": sequences[target_id]})
            for target_id, _ in targets
        ]
        config = {
            "n_pairs": len(rows),
            "iterations": iterations,
            "batch_size": batch_size,
            "top_k": top_k,
            "weights": weights,
            "objective_ports": objective_ports,
            "ablations": [entry["ablation"] for entry in ablations],
            "seeds": seeds,
            "targets_meta": targets_meta,
            "budget_usd": budget_usd,
        }

        output_dir = node_output_dir(self, context)
        pairs_path = output_dir / "pairs.tsv"
        pairs_jsonl_path = output_dir / "pairs.jsonl"
        targets_jsonl_path = output_dir / "targets.jsonl"
        config_path = output_dir / "campaign_config.json"
        weights_path = output_dir / "weights.json"
        ablations_path = output_dir / "ablations.jsonl"
        write_tsv_file(pairs_path, ["pair_id", "target_id", "seed", "cds_sequence"], rows)
        write_jsonl_file(pairs_jsonl_path, jsonl_rows)
        write_jsonl_file(targets_jsonl_path, targets_rows)
        write_json_file(config_path, config)
        write_json_file(weights_path, weights)
        write_jsonl_file(
            ablations_path,
            [
                {"ablation": entry["ablation"], "evaluator_weights": json.dumps(entry["weights"], sort_keys=True)}
                for entry in ablations
            ],
        )
        return (
            str(pairs_path),
            str(pairs_jsonl_path),
            str(targets_jsonl_path),
            str(config_path),
            str(weights_path),
            str(ablations_path),
        )

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
    def _objective_ports(value: Any) -> dict[str, str] | str:
        text = str(value if value not in (None, "") else DEFAULT_OBJECTIVE_PORTS).strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            return f"Input 'objective_ports' must be a JSON object of evaluator name -> scores_N port ({exc})"
        if not isinstance(payload, dict) or not payload:
            return "Input 'objective_ports' must be a non-empty JSON object of evaluator name -> scores_N port"
        for name, port in payload.items():
            if not isinstance(port, str) or not re.fullmatch(r"scores_[1-9]\d*", port):
                return f"Input 'objective_ports' value for '{name}' must be a scores_N port name (got: {port!r})"
        return {str(name): str(port) for name, port in payload.items()}

    @staticmethod
    def _port_weights(weights: dict[str, float], objective_ports: dict[str, str]) -> dict[str, float]:
        return {
            port: weights[name]
            for name, port in sorted(objective_ports.items())
            if name in weights
        }

    @staticmethod
    def _ablations(value: Any, default_weights: dict[str, float]) -> list[dict[str, Any]]:
        text = str(value if value not in (None, "") else "")
        entries: list[dict[str, Any]] = []
        for line_number, raw_line in enumerate(text.replace(";", "\n").splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            fields = line.split("\t") if "\t" in line else line.split(None, 1)
            if len(fields) != 2 or not fields[0].strip() or not fields[1].strip():
                raise ValueError(
                    f"Input 'ablation_weights' line {line_number} must be 'name<TAB>{{\"evaluator\":0.0,...}}' (got: {line!r})"
                )
            name = fields[0].strip()
            try:
                overrides = json.loads(fields[1].strip())
            except json.JSONDecodeError as exc:
                raise ValueError(f"Input 'ablation_weights' line {line_number} override is not valid JSON ({exc})") from exc
            if not isinstance(overrides, dict) or not overrides:
                raise ValueError(
                    f"Input 'ablation_weights' line {line_number} override must be a non-empty JSON object"
                )
            merged = dict(default_weights)
            for evaluator, weight in overrides.items():
                if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(float(weight)):
                    raise ValueError(
                        f"Input 'ablation_weights' line {line_number} weight for '{evaluator}' must be a finite number"
                    )
                if float(weight) < 0:
                    raise ValueError(
                        f"Input 'ablation_weights' line {line_number} weight for '{evaluator}' must be non-negative"
                    )
                merged[str(evaluator)] = float(weight)
            if sum(merged.values()) <= 0:
                raise ValueError(f"Input 'ablation_weights' line {line_number} weights must sum to a positive total")
            entries.append({"ablation": name, "weights": merged})
        return entries

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
