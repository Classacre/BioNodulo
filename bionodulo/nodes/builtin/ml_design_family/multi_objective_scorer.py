"""Group-normalized weighted composite scoring of candidate batches."""

from __future__ import annotations

import json
import math
from typing import Any

from .adapter import (
    MLDesignNode,
    load_json_or_table,
    node_output_dir,
    numeric_field,
    parse_candidates,
    validate_choice_input,
    write_json_file,
    write_tsv_file,
)

SCORE_PORT_COUNT = 4
MODES = ("maximize", "minimize")


class MultiObjectiveScorerNode(MLDesignNode):
    """Fuse evaluator outputs into one z-normalized weighted composite per candidate."""

    NODE_ID = "multi_objective_scorer"
    DISPLAY_NAME = "Multi-Objective Scorer"
    DESCRIPTION = (
        "Combine one to four evaluator score inputs (JSON array of {id, score} or TSV "
        "id/score) into a per-candidate composite: each objective is z-normalized across "
        "the candidate group, sign-flipped for minimize objectives, then weight-averaged. "
        "Output is ranked descending by composite."
    )
    SEARCH_ALIASES = [
        "multi-objective",
        "composite score",
        "weighted sum",
        "z-score normalization",
        "pareto",
        "objective fusion",
    ]
    RETURN_TYPES = ("JSON", "TSV")
    RETURN_NAMES = ("ranked", "table")
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/statistics.html"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        score_ports: dict[str, Any] = {
            f"scores_{index}": (
                "STRING",
                {"description": f"Objective {index}: JSON array of {{id, score}} or TSV with id and score columns"},
            )
            for index in range(1, SCORE_PORT_COUNT + 1)
        }
        return {
            "required": {
                "candidates": ("JSON", {"description": "Candidate batch JSON from candidate_generator or policy_sampler"}),
                "scores_1": score_ports["scores_1"],
            },
            "optional": {
                **{name: port for name, port in score_ports.items() if name != "scores_1"},
                "weights": (
                    "STRING",
                    {
                        "default": "{}",
                        "multiline": True,
                        "description": "JSON object mapping scores_N input name to a non-negative weight",
                    },
                ),
                "modes": (
                    "STRING",
                    {
                        "default": "{}",
                        "multiline": True,
                        "description": "JSON object mapping scores_N input name to maximize|minimize",
                    },
                ),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("weights", "modes"):
            raw = str(inputs.get(key, "") or "{}").strip() or "{}"
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                return f"Input '{key}' must be a JSON object: {exc}"
            if not isinstance(payload, dict):
                return f"Input '{key}' must be a JSON object"
            for name, value in payload.items():
                if name not in {f"scores_{index}" for index in range(1, SCORE_PORT_COUNT + 1)}:
                    return f"Input '{key}' key must be a scores_N input name, got: {name}"
                if key == "weights":
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) < 0:
                        return f"Input 'weights' weight for {name} must be a non-negative number"
                else:
                    check = validate_choice_input(value, f"modes[{name}]", MODES)
                    if check is not True:
                        return check
        return True

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        candidates = parse_candidates(kwargs["candidates"], "candidates")
        candidate_ids = [entry["id"] for entry in candidates]

        objectives: dict[str, dict[str, float]] = {}
        for index in range(1, SCORE_PORT_COUNT + 1):
            name = f"scores_{index}"
            if kwargs.get(name) in (None, ""):
                continue
            objectives[name] = self._parse_objective(kwargs[name], name, candidate_ids)
        if not objectives:
            raise ValueError("At least one scores_N input must be provided")

        weights = self._parameter_map(kwargs.get("weights"), "weights", default=1.0)
        modes = self._parameter_map(kwargs.get("modes"), "modes", default="maximize")
        active = {name: float(weights.get(name, 1.0)) for name in objectives}
        if sum(active.values()) <= 0:
            raise ValueError("Input 'weights' must yield a positive total weight")

        normalized: dict[str, dict[str, float]] = {}
        for name, scores in objectives.items():
            values = [scores[cid] for cid in candidate_ids]
            mean = sum(values) / len(values)
            variance = sum((value - mean) ** 2 for value in values) / len(values)
            std = math.sqrt(variance)
            normalized[name] = {
                cid: 0.0 if std == 0 else (scores[cid] - mean) / std for cid in candidate_ids
            }

        ranked: list[dict[str, Any]] = []
        total_weight = sum(active.values())
        for entry in candidates:
            cid = entry["id"]
            composite = 0.0
            per_objective: dict[str, float] = {}
            for name in objectives:
                direction = 1.0 if modes.get(name, "maximize") == "maximize" else -1.0
                composite += active[name] * direction * normalized[name][cid]
                per_objective[name] = objectives[name][cid]
            composite = composite / total_weight
            ranked.append({"id": cid, "composite": composite, "per_objective": per_objective})
        ranked.sort(key=lambda item: (-item["composite"], item["id"]))

        output_dir = node_output_dir(self, context)
        json_path = output_dir / "ranked.json"
        tsv_path = output_dir / "ranked.tsv"
        write_json_file(json_path, ranked)
        objective_names = list(objectives)
        write_tsv_file(
            tsv_path,
            ["id", "composite", *objective_names],
            [
                {
                    "id": item["id"],
                    "composite": item["composite"],
                    **{name: item["per_objective"][name] for name in objective_names},
                }
                for item in ranked
            ],
        )
        return (str(json_path), str(tsv_path))

    @staticmethod
    def _parse_objective(value: Any, name: str, candidate_ids: list[str]) -> dict[str, float]:
        payload, table = load_json_or_table(value, name)
        if payload is not None:
            if not isinstance(payload, list) or not payload:
                raise ValueError(f"Input '{name}' must be a non-empty JSON array of {{id, score}}")
            scores: dict[str, float] = {}
            for index, entry in enumerate(payload):
                if not isinstance(entry, dict):
                    raise ValueError(f"Input '{name}' entry {index} must be a JSON object")
                cid = str(entry.get("id", "")).strip()
                if not cid:
                    raise ValueError(f"Input '{name}' entry {index} is missing a non-empty 'id'")
                if cid in scores:
                    raise ValueError(f"Input '{name}' contains duplicate id: {cid}")
                scores[cid] = numeric_field(entry, "score", f"Input '{name}' entry {cid}")
        else:
            fieldnames, rows = table if table is not None else ([], [])
            for column in ("id", "score"):
                if column not in fieldnames:
                    raise ValueError(f"Input '{name}' TSV header must contain an '{column}' column")
            scores = {
                row["id"].strip(): numeric_field(row, "score", f"Input '{name}' row {row['id']}")
                for row in rows
            }
            if len(scores) != len(rows):
                raise ValueError(f"Input '{name}' TSV contains duplicate id values")
        missing = [cid for cid in candidate_ids if cid not in scores]
        if missing:
            raise ValueError(
                f"Input '{name}' is missing scores for {len(missing)} candidate(s): {', '.join(missing[:10])}"
            )
        unknown = sorted(set(scores) - set(candidate_ids))
        if unknown:
            raise ValueError(
                f"Input '{name}' contains {len(unknown)} id(s) absent from candidates: {', '.join(unknown[:10])}"
            )
        return {cid: scores[cid] for cid in candidate_ids}

    @staticmethod
    def _parameter_map(value: Any, key: str, *, default: Any) -> dict[str, Any]:
        raw = str(value or "{}").strip() or "{}"
        payload = json.loads(raw)
        return {name: payload.get(name, default) for name in payload}
