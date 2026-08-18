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


def _optional_number(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return ""
    number = float(value)
    return f"{number:.6f}" if math.isfinite(number) else ""


class CampaignResultsBuilderNode(MLDesignNode):
    """Collect per-iteration optimizer, policy, and evaluator rows from a run tree."""

    NODE_ID = "campaign_results_builder"
    DISPLAY_NAME = "Campaign Results Builder"
    DESCRIPTION = (
        "Walks a completed design-campaign run directory, scanning '<run_dir>/**/"
        "iterations/NNNN/' recursively. For each iteration directory it emits: the "
        "relative subgraph path (the branch holding the 'iterations' folder) and "
        "iteration number; best_composite, mean, and improvement_vs_prev from any "
        "group_relative_optimizer elites.json (falling back to the composite of the "
        "best_so_far/best.json argmax tracker when a loop has no optimizer, e.g. "
        "random-search baselines); mean Shannon entropy (natural log) over the "
        "codon->probability positions of policy_table.json; and the mean of every "
        "numeric score column of each evaluator TSV/CSV table found in the same "
        "iteration (grouped per file basename). Output is a long-format "
        "campaign_results.csv (subgraph, iteration, evaluator, metric, value), "
        "summary.json totals, and a per_subgraph.tsv with one row per loop branch "
        "(iterations, best composite overall/final, best id, and the final best "
        "candidate's raw per-objective scores best_scores_1..best_scores_6) for "
        "paired method comparisons. Empty run_dir resolves to the executor's "
        "runs/<run_id> root so a master-level node can scan every phase subgraph in "
        "one pass; the 'after' list input is a completion barrier for provenance. "
        "Pure stdlib globbing; empty trees are an error."
    )
    SEARCH_ALIASES = [
        "campaign results",
        "run summary",
        "sweep aggregation",
        "elites",
        "policy entropy",
        "iteration log",
    ]
    RETURN_TYPES = ("CSV", "JSON", "TSV")
    RETURN_NAMES = ("results", "summary", "per_subgraph")
    EXECUTOR_CACHE_POLICY = "always_run"
    N_SCORE_COLUMNS = 6

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {},
            "optional": {
                "run_dir": (
                    "STRING",
                    {"default": "", "description": "Completed campaign run directory; empty uses the executor's runs/<run_id> root"},
                ),
                "after": (
                    "LIST",
                    {
                        "default": [],
                        "description": "Completion barrier: subgraph_dir outputs of phases this scan must run after (recorded as provenance)",
                    },
                ),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str, str, str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        run_dir_text = str(kwargs.get("run_dir", "") or "").strip()
        if run_dir_text:
            run_dir = Path(run_dir_text).expanduser()
        else:
            workspace = Path(getattr(context, "workspace_dir", "") or ".")
            run_id = str(getattr(context, "run_id", "") or "")
            if not run_id:
                raise ValueError("Input 'run_dir' is required when the node runs outside an execution context")
            run_dir = workspace / "runs" / run_id
        if not run_dir.is_dir():
            raise ValueError(f"Input 'run_dir' is not an existing directory: {run_dir}")

        rows: list[dict[str, Any]] = []
        iterations_by_subgraph: dict[str, set[int]] = {}
        best_by_iteration: dict[tuple[str, int], float] = {}
        best_record_by_subgraph: dict[str, dict[str, Any]] = {}
        for iteration_dir in self._iteration_dirs(run_dir):
            branch = iteration_dir.parent.parent
            subgraph = branch.relative_to(run_dir).as_posix()
            iteration = int(iteration_dir.name)
            iterations_by_subgraph.setdefault(subgraph, set()).add(iteration)
            for metric, value in self._optimizer_metrics(iteration_dir):
                rows.append(self._row(subgraph, iteration, "elites", metric, value))
                if metric == "best_composite" and value is not None:
                    best_by_iteration.setdefault((subgraph, iteration), float(value))
            for metric, value in self._best_so_far_metrics(iteration_dir):
                rows.append(self._row(subgraph, iteration, "best_so_far", metric, value))
                if metric == "composite" and value is not None:
                    best_by_iteration.setdefault((subgraph, iteration), float(value))
            best_payload = self._best_payload(iteration_dir)
            if best_payload is not None:
                # Iteration dirs arrive in ascending order; the last write wins so
                # best_id/best_scores_* reflect the loop's final argmax.
                best_record_by_subgraph[subgraph] = best_payload
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
        after = kwargs.get("after")
        after_paths = [str(item) for item in after] if isinstance(after, (list, tuple)) else []
        summary = {
            "run_dir": str(run_dir),
            "after": after_paths,
            "n_subgraphs": len(subgraphs),
            "n_iterations": sum(len(entry["iterations"]) for entry in subgraphs),
            "n_rows": len(rows),
            "subgraphs": subgraphs,
        }

        output_dir = node_output_dir(self, context)
        results_path = output_dir / "campaign_results.csv"
        summary_path = output_dir / "summary.json"
        per_subgraph_path = output_dir / "per_subgraph.tsv"
        self._write_csv(results_path, rows)
        write_json_file(summary_path, summary)
        self._write_per_subgraph(per_subgraph_path, subgraphs, best_record_by_subgraph)
        return (str(results_path), str(summary_path), str(per_subgraph_path))

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
    def _best_payload(iteration_dir: Path) -> dict[str, Any] | None:
        """Final best record for a branch: best_so_far best.json preferred (it keeps raw per_objective)."""
        for path in sorted(iteration_dir.rglob("best.json")):
            if path.parent.name != "best_so_far" or not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return None
            return payload if isinstance(payload, dict) else None
        for path in sorted(iteration_dir.rglob("best.json")):
            if path.parent.name != OPTIMIZER_DIR or not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return None
            return payload if isinstance(payload, dict) else None
        return None

    @staticmethod
    def _best_so_far_metrics(iteration_dir: Path) -> list[tuple[str, Any]]:
        payload = CampaignResultsBuilderNode._best_payload(iteration_dir)
        if payload is None or not isinstance(payload.get("composite"), (int, float)):
            return []
        return [("composite", float(payload["composite"]))]

    @classmethod
    def _write_per_subgraph(
        cls,
        path: Path,
        subgraphs: list[dict[str, Any]],
        best_records: dict[str, dict[str, Any]],
    ) -> None:
        fieldnames = [
            "subgraph",
            "n_iterations",
            "best_composite_overall",
            "best_composite_final",
            "best_id",
            *[f"best_scores_{index}" for index in range(1, cls.N_SCORE_COLUMNS + 1)],
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            writer.writerow(fieldnames)
            for entry in subgraphs:
                record = best_records.get(entry["subgraph"], {})
                per_objective = record.get("per_objective", {}) if isinstance(record.get("per_objective"), dict) else {}
                scores = [
                    per_objective.get(f"scores_{index}") for index in range(1, cls.N_SCORE_COLUMNS + 1)
                ]
                writer.writerow(
                    [
                        entry["subgraph"],
                        len(entry["iterations"]),
                        _optional_number(entry["best_composite_overall"]),
                        _optional_number(entry["best_composite_final"]),
                        str(record.get("id", "") or ""),
                        *[_optional_number(value) for value in scores],
                    ]
                )

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
