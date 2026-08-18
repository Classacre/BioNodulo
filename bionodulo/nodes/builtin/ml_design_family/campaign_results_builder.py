"""Aggregate a completed design-campaign run tree into one table + totals."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from .adapter import MLDesignNode, node_output_dir, read_table, write_json_file

OPTIMIZER_DIR = "group_relative_optimizer"
ELITE_METRICS = ("best_composite", "mean", "improvement_vs_prev")


class CampaignResultsBuilderNode(MLDesignNode):
    """Collect per-iteration optimizer, policy, and evaluator rows from a run tree."""

    NODE_ID = "campaign_results_builder"
    DISPLAY_NAME = "Campaign Results Builder"
    DESCRIPTION = (
        "Walks a completed design-campaign run directory, scanning '<run_dir>/**/"
        "iterations/NNNN/' recursively. For each iteration directory it emits: the "
        "relative subgraph path (the branch holding the 'iterations' folder) and "
        "iteration number; best_composite, mean, and improvement_vs_prev from any "
        "group_relative_optimizer elites.json; mean Shannon entropy (natural log) "
        "over the codon->probability positions of policy_table.json; and the mean "
        "of every numeric score column of each evaluator TSV/CSV table found in the "
        "same iteration (grouped per file basename). Output is a long-format "
        "campaign_results.csv (subgraph, iteration, evaluator, metric, value) plus "
        "summary.json totals. Pure stdlib globbing; empty trees are an error."
    )
    SEARCH_ALIASES = [
        "campaign results",
        "run summary",
        "sweep aggregation",
        "elites",
        "policy entropy",
        "iteration log",
    ]
    RETURN_TYPES = ("CSV", "JSON")
    RETURN_NAMES = ("results", "summary")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "run_dir": (
                    "STRING",
                    {"description": "Path to a completed campaign run directory containing iterations/NNNN trees"},
                ),
            },
            "optional": {},
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        run_dir = Path(str(kwargs["run_dir"]).strip()).expanduser()
        if not run_dir.is_dir():
            raise ValueError(f"Input 'run_dir' is not an existing directory: {run_dir}")

        rows: list[dict[str, Any]] = []
        iterations_by_subgraph: dict[str, set[int]] = {}
        best_by_iteration: dict[tuple[str, int], float] = {}
        for iteration_dir in self._iteration_dirs(run_dir):
            branch = iteration_dir.parent.parent
            subgraph = branch.relative_to(run_dir).as_posix()
            iteration = int(iteration_dir.name)
            iterations_by_subgraph.setdefault(subgraph, set()).add(iteration)
            for metric, value in self._optimizer_metrics(iteration_dir):
                rows.append(self._row(subgraph, iteration, "elites", metric, value))
                if metric == "best_composite" and value is not None:
                    best_by_iteration.setdefault((subgraph, iteration), float(value))
            entropy = self._policy_entropy(iteration_dir)
            if entropy is not None:
                rows.append(self._row(subgraph, iteration, "policy_table", "mean_entropy", entropy))
            for evaluator, metric, value in self._evaluator_metrics(iteration_dir):
                rows.append(self._row(subgraph, iteration, evaluator, metric, value))

        if not rows:
            raise ValueError(f"No iterations/NNNN content found under run_dir: {run_dir}")

        subgraphs = []
        for subgraph in sorted(iterations_by_subgraph):
            best_composites = [
                best_by_iteration[(subgraph, iteration)]
                for iteration in sorted(iterations_by_subgraph[subgraph])
                if (subgraph, iteration) in best_by_iteration
            ]
            subgraphs.append(
                {
                    "subgraph": subgraph,
                    "iterations": sorted(iterations_by_subgraph[subgraph]),
                    "best_composite_overall": max(best_composites) if best_composites else None,
                    "best_composite_final": best_composites[-1] if best_composites else None,
                }
            )
        summary = {
            "n_subgraphs": len(subgraphs),
            "n_iterations": sum(len(entry["iterations"]) for entry in subgraphs),
            "n_rows": len(rows),
            "subgraphs": subgraphs,
        }

        output_dir = node_output_dir(self, context)
        results_path = output_dir / "campaign_results.csv"
        summary_path = output_dir / "summary.json"
        self._write_csv(results_path, rows)
        write_json_file(summary_path, summary)
        return (str(results_path), str(summary_path))

    @staticmethod
    def _row(subgraph: str, iteration: int, evaluator: str, metric: str, value: Any) -> dict[str, Any]:
        return {
            "subgraph": subgraph,
            "iteration": iteration,
            "evaluator": evaluator,
            "metric": metric,
            "value": None if value is None else float(value),
        }

    @staticmethod
    def _iteration_dirs(run_dir: Path) -> list[Path]:
        found: list[Path] = []
        for iterations_dir in sorted(run_dir.glob("**/iterations")):
            if not iterations_dir.is_dir():
                continue
            for child in sorted(iterations_dir.iterdir()):
                if child.is_dir() and child.name.isdigit():
                    found.append(child)
        return sorted(found, key=lambda path: (path.parent.parent.relative_to(run_dir).as_posix(), int(path.name)))

    @staticmethod
    def _optimizer_metrics(iteration_dir: Path) -> list[tuple[str, Any]]:
        for path in sorted(iteration_dir.rglob("elites.json")):
            if path.parent.name != OPTIMIZER_DIR or not path.is_file():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            stats = payload.get("stats", {}) if isinstance(payload, dict) else {}
            return [(metric, stats.get(metric)) for metric in ELITE_METRICS]
        return []

    @staticmethod
    def _policy_entropy(iteration_dir: Path) -> float | None:
        for path in sorted(iteration_dir.rglob("policy_table.json")):
            if path.parent.name != OPTIMIZER_DIR or not path.is_file():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            positions = payload.get("positions", {}) if isinstance(payload, dict) else {}
            if not isinstance(positions, dict) or not positions:
                return None
            entropies: list[float] = []
            for distribution in positions.values():
                if not isinstance(distribution, dict):
                    continue
                weights = [float(weight) for weight in distribution.values() if isinstance(weight, (int, float)) and weight > 0]
                total = sum(weights)
                if total <= 0:
                    continue
                entropies.append(-sum(probability * math.log(probability) for probability in (weight / total for weight in weights)))
            return sum(entropies) / len(entropies) if entropies else None
        return None

    @staticmethod
    def _evaluator_metrics(iteration_dir: Path) -> list[tuple[str, str, float]]:
        outputs: list[tuple[str, str, float]] = []
        tables = sorted(list(iteration_dir.rglob("*.tsv")) + list(iteration_dir.rglob("*.csv")))
        for path in tables:
            if not path.is_file() or OPTIMIZER_DIR in path.relative_to(iteration_dir).parts:
                continue
            try:
                fieldnames, table_rows = read_table(path)
            except ValueError:
                continue
            for column in fieldnames:
                values: list[float] = []
                for row in table_rows:
                    try:
                        number = float(str(row.get(column, "")).strip())
                    except ValueError:
                        values = []
                        break
                    if not math.isfinite(number):
                        values = []
                        break
                    values.append(number)
                if values:
                    outputs.append((path.stem, column, sum(values) / len(values)))
        return outputs

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
        fieldnames = ["subgraph", "iteration", "evaluator", "metric", "value"]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(fieldnames)
            for row in rows:
                value = row["value"]
                writer.writerow(
                    [
                        row["subgraph"],
                        row["iteration"],
                        row["evaluator"],
                        row["metric"],
                        "" if value is None else f"{value:.6f}",
                    ]
                )
