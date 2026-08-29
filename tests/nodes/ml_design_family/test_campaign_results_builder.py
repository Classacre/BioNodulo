from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.nodes.builtin.ml_design_family import CampaignResultsBuilderNode

SUBGRAPHS = ("sub_a", "sub_b")
ITERATIONS = ("0000", "0001", "0002")


def _context(tmp_path: Path, name: str = "run") -> SimpleNamespace:
    node_dir = tmp_path / name
    node_dir.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(node_dir=node_dir)


def _build_tree(run_dir: Path) -> None:
    for subgraph in SUBGRAPHS:
        for index, iteration in enumerate(ITERATIONS):
            iteration_dir = run_dir / subgraph / "iterations" / iteration
            optimizer_dir = iteration_dir / "group_relative_optimizer"
            optimizer_dir.mkdir(parents=True, exist_ok=True)
            best = 10.0 + index + (0.5 if subgraph == "sub_b" else 0.0)
            (optimizer_dir / "elites.json").write_text(
                json.dumps(
                    {
                        "elites": [],
                        "best": {"id": "cand_0000", "composite": best},
                        "stats": {
                            "mean": best - 1.0,
                            "std": 0.25,
                            "best_composite": best,
                            "improvement_vs_prev": None if index == 0 else 0.5,
                        },
                    }
                ),
                encoding="utf-8",
            )
            (optimizer_dir / "policy_table.json").write_text(
                json.dumps(
                    {
                        "positions": {
                            "0": {"AAA": 0.5, "AAG": 0.5},
                            "1": {"CCC": 1.0},
                        }
                    }
                ),
                encoding="utf-8",
            )
            evaluator_dir = iteration_dir / "gc_evaluator"
            evaluator_dir.mkdir(parents=True, exist_ok=True)
            (evaluator_dir / "table.tsv").write_text(
                "id\tgc\nE1\t0.5\nE2\t0.4\nE3\t0.6\n",
                encoding="utf-8",
            )


@pytest.mark.asyncio
async def test_two_subgraphs_three_iterations(tmp_path: Path) -> None:
    run_dir = tmp_path / "campaign"
    _build_tree(run_dir)
    node = CampaignResultsBuilderNode()
    results_path, summary_path, per_subgraph_path = await node.run(run_dir=str(run_dir), context=_context(tmp_path))

    with Path(results_path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 30
    by_key = {(row["subgraph"], row["iteration"], row["evaluator"], row["metric"]): row["value"] for row in rows}
    assert by_key[("sub_a", "2", "elites", "best_composite")] == "12.000000"
    assert by_key[("sub_b", "0", "elites", "best_composite")] == "10.500000"
    assert by_key[("sub_a", "1", "elites", "mean")] == "10.000000"
    assert by_key[("sub_a", "0", "elites", "improvement_vs_prev")] == ""
    assert by_key[("sub_a", "2", "elites", "improvement_vs_prev")] == "0.500000"
    expected_entropy = (math.log(2.0) + 0.0) / 2
    assert float(by_key[("sub_b", "1", "policy_table", "mean_entropy")]) == pytest.approx(expected_entropy, abs=1e-6)
    assert float(by_key[("sub_a", "0", "table", "gc")]) == pytest.approx(0.5)

    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    assert summary["n_subgraphs"] == 2
    assert summary["n_iterations"] == 6
    assert summary["n_rows"] == 30
    by_subgraph = {entry["subgraph"]: entry for entry in summary["subgraphs"]}
    assert by_subgraph["sub_a"]["iterations"] == [0, 1, 2]
    assert by_subgraph["sub_a"]["best_composite_overall"] == pytest.approx(12.0)
    assert by_subgraph["sub_a"]["best_composite_final"] == pytest.approx(12.0)
    assert by_subgraph["sub_b"]["best_composite_overall"] == pytest.approx(12.5)
    assert by_subgraph["sub_b"]["best_composite_final"] == pytest.approx(12.5)


@pytest.mark.asyncio
async def test_subgraph_path_is_relative_branch(tmp_path: Path) -> None:
    run_dir = tmp_path / "nested"
    _build_tree(run_dir)
    node = CampaignResultsBuilderNode()
    results_path, _, _ = await node.run(run_dir=str(run_dir), context=_context(tmp_path, "nested"))
    with Path(results_path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["subgraph"] for row in rows} == {"sub_a", "sub_b"}
    assert {int(row["iteration"]) for row in rows} == {0, 1, 2}


@pytest.mark.asyncio
async def test_empty_and_missing_run_dirs(tmp_path: Path) -> None:
    node = CampaignResultsBuilderNode()
    with pytest.raises(ValueError, match="not an existing directory"):
        await node.run(run_dir=str(tmp_path / "nowhere"), context=_context(tmp_path))
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="No iterations"):
        await node.run(run_dir=str(empty), context=_context(tmp_path, "empty"))


def _build_best_so_far_tree(run_dir: Path) -> None:
    """A baseline loop without an optimizer: best_so_far best.json per iteration."""
    for index in range(2):
        iteration_dir = run_dir / "fe_b1" / "iterations" / f"{index:04d}"
        best_dir = iteration_dir / "best_so_far"
        best_dir.mkdir(parents=True, exist_ok=True)
        (best_dir / "best.json").write_text(
            json.dumps(
                {
                    "id": "cand_0001",
                    "composite": 5.0 + index,
                    "per_objective": {"scores_1": 0.4, "scores_4": 12.5},
                }
            ),
            encoding="utf-8",
        )


@pytest.mark.asyncio
async def test_per_subgraph_rows_capture_best_so_far_baselines(tmp_path: Path) -> None:
    run_dir = tmp_path / "campaign_b1"
    _build_best_so_far_tree(run_dir)
    node = CampaignResultsBuilderNode()

    results_path, summary_path, per_subgraph_path = await node.run(
        run_dir=str(run_dir), after=["/runs/x/e1"], context=_context(tmp_path)
    )

    lines = Path(per_subgraph_path).read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    assert header[:5] == ["subgraph", "n_iterations", "best_composite_overall", "best_composite_final", "best_id"]
    assert header[5:] == [f"best_scores_{index}" for index in range(1, 7)]
    row = dict(zip(header, lines[1].split("\t"), strict=True))
    assert row["subgraph"] == "fe_b1"
    assert row["n_iterations"] == "2"
    assert row["best_composite_overall"] == "6.000000"
    assert row["best_composite_final"] == "6.000000"
    assert row["best_id"] == "cand_0001"
    assert row["best_scores_1"] == "0.400000"
    assert row["best_scores_4"] == "12.500000"
    assert row["best_scores_2"] == ""

    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    assert summary["after"] == ["/runs/x/e1"]
    assert summary["run_dir"] == str(run_dir)
    assert summary["subgraphs"][0]["best_composite_overall"] == pytest.approx(6.0)
    with Path(results_path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert {(row["evaluator"], row["metric"]) for row in rows} == {("best_so_far", "composite")}


@pytest.mark.asyncio
async def test_empty_run_dir_uses_execution_context_runs_root(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = workspace / "runs" / "run-42"
    _build_best_so_far_tree(run_dir)
    context = SimpleNamespace(node_dir=tmp_path / "node", workspace_dir=workspace, run_id="run-42")
    node = CampaignResultsBuilderNode()

    _, summary_path, _ = await node.run(run_dir="", context=context)

    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    assert summary["run_dir"] == str(run_dir)
    assert summary["n_subgraphs"] == 1

    bare = SimpleNamespace(node_dir=tmp_path / "node2")
    with pytest.raises(ValueError, match="outside an execution context"):
        await node.run(run_dir="", context=bare)


def test_replayed_iterations_resolve_through_pointer_files(tmp_path):
    """Fully-cached branches materialise no elites.json/best.json under the
    new run; the executor writes replay.json pointers instead (seen live when
    LinearDesign's per-target rows came back empty in the campaign summary).
    The builder follows the pointers; direct scans keep priority when real
    files exist."""
    import json as _json

    from bionodulo.nodes.builtin.ml_design_family.campaign_results_builder import (
        CampaignResultsBuilderNode as CRB,
    )

    orig = tmp_path / "orig"
    orig.mkdir()
    (orig / "elites.json").write_text(
        _json.dumps({"stats": {"best_composite": 1.234}}), encoding="utf-8"
    )
    (orig / "best.json").write_text(
        _json.dumps({"composite": 1.234, "id": "cand_9", "best_cds": "ATGCCC"}),
        encoding="utf-8",
    )
    it = tmp_path / "run" / "branch" / "iterations" / "0001"
    (it / "group_relative_optimizer").mkdir(parents=True)
    (it / "best_so_far").mkdir(parents=True)
    (it / "group_relative_optimizer" / "replay.json").write_text(
        _json.dumps({"cache_key": "k1", "outputs": {"metrics": str(orig / "elites.json")}}),
        encoding="utf-8",
    )
    (it / "best_so_far" / "replay.json").write_text(
        _json.dumps({"cache_key": "k2", "outputs": {"best": str(orig / "best.json")}}),
        encoding="utf-8",
    )
    metrics = CRB._optimizer_metrics(it)
    assert metrics and metrics[0][1] == 1.234
    best = CRB._best_payload(it)
    assert best and best["best_cds"] == "ATGCCC"

    live = tmp_path / "live"
    (live / "group_relative_optimizer").mkdir(parents=True)
    (live / "group_relative_optimizer" / "elites.json").write_text(
        _json.dumps({"stats": {"best_composite": 9.9}}), encoding="utf-8"
    )
    assert CRB._optimizer_metrics(live)[0][1] == 9.9
