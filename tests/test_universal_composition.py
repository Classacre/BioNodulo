"""Engine-level universal composition tests.

Any workflow that composes loops + subgraphs + evaluators + joins + scorers
must survive its first iteration — empty candidate batches flowing through
evaluators, joins, scorers, optimizers, and trackers — emitting empty results
that downstream nodes also tolerate. These tests exercise the ENGINE contract
with builtin nodes directly, independent of any one template's authoring.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.nodes.builtin.data_transform_family.adapter import read_table as dt_read_table
from bionodulo.nodes.builtin.data_transform_family.join_tables import JoinTablesNode
from bionodulo.nodes.builtin.ml_design_family.adapter import read_table as ml_read_table
from bionodulo.nodes.builtin.ml_design_family.best_so_far import BestSoFarNode
from bionodulo.nodes.builtin.ml_design_family.candidate_generator import CandidateGeneratorNode
from bionodulo.nodes.builtin.ml_design_family.group_relative_optimizer import GroupRelativeOptimizerNode
from bionodulo.nodes.builtin.ml_design_family.multi_objective_scorer import MultiObjectiveScorerNode
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.workflow.validation import validate_workflow

BASE_CDS = "ATGGCTAAATTTGGCTTTGTTCAAGGACGATCAGTCGTG"  # codon-diverse, no stop codons


def _registry() -> NodeRegistry:
    registry = NodeRegistry()
    registry.load_builtin_nodes()
    return registry


def _context(tmp_path: Path, name: str) -> Any:
    return type("Ctx", (), {"node_dir": tmp_path / name})()


# ---------------------------------------------------------------------------
# table readers: header-only + provenance-footer semantics
# ---------------------------------------------------------------------------


def test_header_only_tables_read_as_empty_in_both_families(tmp_path: Path) -> None:
    header_only = tmp_path / "header_only.tsv"
    header_only.write_text("id\tscore\n", encoding="utf-8")

    # Both families treat a valid-header/zero-row table as empty: the
    # ml_design reader collapses to ([], []), the data_transform reader keeps
    # its header but reports zero data rows.
    assert ml_read_table(header_only) == ([], [])
    assert dt_read_table(header_only, "\t") == (["id", "score"], [])

    # A file with no header at all is still an error (nothing was declared).
    no_header = tmp_path / "no_header.tsv"
    no_header.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="Table is empty"):
        ml_read_table(no_header)
    with pytest.raises(ValueError, match="Table is empty"):
        dt_read_table(no_header, "\t")


def test_provenance_footer_tables_yield_data_rows_only(tmp_path: Path) -> None:
    table = tmp_path / "with_footer.tsv"
    table.write_text(
        "id\tscore\n"
        "a\t1.0\n"
        "b\t2.0\n"
        "<!-- BioNodulo provenance: everything below is metadata -->\n"
        "ignored\trow\n",
        encoding="utf-8",
    )

    for reader in (lambda p: ml_read_table(p), lambda p: dt_read_table(p, "\t")):
        fieldnames, rows = reader(table)
        assert fieldnames == ["id", "score"]
        assert [row["id"] for row in rows] == ["a", "b"]


# ---------------------------------------------------------------------------
# empty table -> join -> scorer -> optimizer chain (direct node composition)
# ---------------------------------------------------------------------------


async def _candidates(tmp_path: Path, name: str, n: int = 4) -> str:
    path, _ = await CandidateGeneratorNode().run(
        base_cds=BASE_CDS, n_candidates=n, seed=7, context=_context(tmp_path, name)
    )
    return path


@pytest.mark.asyncio
async def test_empty_tables_flow_through_join_scorer_optimizer_tracker(tmp_path: Path) -> None:
    empty_a = tmp_path / "empty_a.tsv"
    empty_a.write_text("id\tgc\n", encoding="utf-8")
    empty_b = tmp_path / "empty_b.tsv"
    empty_b.write_text("id\tcai\n", encoding="utf-8")

    # join: ANY empty input -> header-only joined table + provenance footer.
    joined = (
        await JoinTablesNode().run(
            table_a=empty_a, table_b=empty_b, join_keys="id", context=_context(tmp_path, "join")
        )
    )[0]
    joined_lines = Path(joined).read_text(encoding="utf-8").splitlines()
    assert joined_lines[0].split("\t") == ["id", "gc", "cai"]
    assert joined_lines[1].startswith("<!-- empty join:")
    # The joined output reads back as an empty table (footer is not data).
    assert dt_read_table(Path(joined), "\t")[1] == []

    # A completely empty (headerless) input also degrades to an empty join.
    headerless = tmp_path / "headerless.tsv"
    headerless.write_text("", encoding="utf-8")
    joined2 = (
        await JoinTablesNode().run(
            table_a=empty_a, table_b=headerless, join_keys="id", context=_context(tmp_path, "join2")
        )
    )[0]
    assert dt_read_table(Path(joined2), "\t")[1] == []

    candidates = await _candidates(tmp_path, "gen")

    # scorer: empty score tables (and/or an empty candidate batch) -> empty ranked.
    empty_ranked, empty_table = await MultiObjectiveScorerNode().run(
        candidates=candidates, scores_1=empty_a, context=_context(tmp_path, "scorer")
    )
    assert json.loads(Path(empty_ranked).read_text(encoding="utf-8")) == []
    table_lines = Path(empty_table).read_text(encoding="utf-8").splitlines()
    assert table_lines[0].split("\t") == ["id", "composite"]
    assert any(line.startswith("<!--") for line in table_lines[1:])

    zero_candidates = await _candidates(tmp_path, "gen0", n=0)
    assert json.loads(Path(zero_candidates).read_text(encoding="utf-8")) == []
    zero_ranked, _ = await MultiObjectiveScorerNode().run(
        candidates=zero_candidates, scores_1=empty_a, context=_context(tmp_path, "scorer0")
    )
    assert json.loads(Path(zero_ranked).read_text(encoding="utf-8")) == []

    # optimizer: zero elites -> unchanged (empty-uniform) policy + null best.
    policy, elites, best = await GroupRelativeOptimizerNode().run(
        candidates=candidates, ranked=empty_ranked, context=_context(tmp_path, "opt")
    )
    policy_payload = json.loads(Path(policy).read_text(encoding="utf-8"))
    assert policy_payload["positions"] == {}
    elites_payload = json.loads(Path(elites).read_text(encoding="utf-8"))
    assert elites_payload["elites"] == []
    assert elites_payload["best"] is None
    assert elites_payload["stats"]["n_candidates"] == 0
    assert elites_payload["stats"]["best_composite"] is None
    assert json.loads(Path(best).read_text(encoding="utf-8")) is None

    # best_so_far: empty incoming passes the current best through (or null).
    null_best, improved, score = await BestSoFarNode().run(
        incoming=empty_ranked, context=_context(tmp_path, "bsf0")
    )
    assert json.loads(Path(null_best).read_text(encoding="utf-8")) is None
    assert improved is False and score == 0.0

    current = tmp_path / "current.json"
    current.write_text(json.dumps({"id": "keep", "composite": 5.0}), encoding="utf-8")
    kept_best, improved, score = await BestSoFarNode().run(
        incoming=empty_ranked, current=current, context=_context(tmp_path, "bsf1")
    )
    assert json.loads(Path(kept_best).read_text(encoding="utf-8"))["id"] == "keep"
    assert improved is False and score == 5.0


@pytest.mark.asyncio
async def test_optimizer_recovers_on_the_iteration_after_an_empty_one(tmp_path: Path) -> None:
    """Iteration 1 empty -> pass-through skeleton policy; iteration 2 with real
    scores updates from the uniform reference instead of failing on the
    skeleton's empty positions."""
    candidates = await _candidates(tmp_path, "gen")

    empty_policy, _, _ = await GroupRelativeOptimizerNode().run(
        candidates=candidates,
        ranked=json.dumps([]),
        context=_context(tmp_path, "opt_empty"),
    )
    assert json.loads(Path(empty_policy).read_text(encoding="utf-8"))["positions"] == {}

    entries = json.loads(Path(candidates).read_text(encoding="utf-8"))
    scores = json.dumps([{"id": entry["id"], "score": float(index)} for index, entry in enumerate(entries)])
    ranked, _ = await MultiObjectiveScorerNode().run(
        candidates=candidates, scores_1=scores, context=_context(tmp_path, "scorer_real")
    )
    assert len(json.loads(Path(ranked).read_text(encoding="utf-8"))) == len(entries)

    policy, elites, best = await GroupRelativeOptimizerNode().run(
        candidates=candidates, ranked=ranked, policy_table=empty_policy, context=_context(tmp_path, "opt_real")
    )
    policy_payload = json.loads(Path(policy).read_text(encoding="utf-8"))
    assert policy_payload["n_positions"] == len(entries[0]["cds"]) // 3
    stats = json.loads(Path(elites).read_text(encoding="utf-8"))["stats"]
    assert stats["n_candidates"] == len(entries)
    assert stats["best_composite"] is not None
    assert json.loads(Path(best).read_text(encoding="utf-8"))["id"]


# ---------------------------------------------------------------------------
# executor: input-node outputs are run-scoped, never served from a dead run
# ---------------------------------------------------------------------------


def _input_join_workflow(source: Path, other: Path) -> dict[str, Any]:
    return {
        "nodes": [
            {"id": "in", "type": "input_file", "params": {"file": str(source)}, "outputs": {"file": {}}},
            {
                "id": "join",
                "type": "join_tables",
                "params": {"table_b": str(other), "join_keys": ""},
                "outputs": {"joined_table": {}},
            },
        ],
        "edges": [
            {
                "source_node": "in",
                "target_node": "join",
                "source_output": "file",
                "target_input": "table_a",
            }
        ],
    }


@pytest.mark.asyncio
async def test_input_node_outputs_are_never_cached_across_runs(tmp_path: Path) -> None:
    source = tmp_path / "source.tsv"
    source.write_text("id\tv\na\t1\n", encoding="utf-8")
    other = tmp_path / "other.tsv"
    other.write_text("id\tw\na\t2\n", encoding="utf-8")
    workflow = _input_join_workflow(source, other)
    assert validate_workflow(workflow, _registry()).valid is True

    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=_registry())

    first = await executor.execute("run-a", copy_wf(workflow))
    assert first["status"] == "completed", first.get("node_results")
    staged_first = Path(first["node_results"]["in"]["outputs"]["file"])
    assert staged_first.is_relative_to(tmp_path / "runs" / "run-a")

    # Simulate run cleanup: the first run's directory disappears.
    shutil.rmtree(tmp_path / "runs" / "run-a")

    second = await executor.execute("run-b", copy_wf(workflow))
    assert second["status"] == "completed", second.get("node_results")
    staged_second = Path(second["node_results"]["in"]["outputs"]["file"])
    # The second run staged its own copy under ITS run directory; the input
    # node never served the deleted first-run path from cache.
    assert staged_second.is_relative_to(tmp_path / "runs" / "run-b")
    assert staged_second.is_file()
    joined = Path(second["node_results"]["join"]["outputs"]["joined_table"])
    assert joined.is_file() and dt_read_table(joined, "\t")[1]


def copy_wf(workflow: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(workflow))


# ---------------------------------------------------------------------------
# executor: while_loop body whose evaluator emits empty per-record tables
# ---------------------------------------------------------------------------


def _empty_evaluator_loop_workflow(marker: Path) -> dict[str, Any]:
    inner = {
        "nodes": [
            {
                "id": "gen",
                "type": "candidate_generator",
                "params": {"base_cds": BASE_CDS, "n_candidates": 4, "seed": 7},
                "outputs": {"candidates": {}, "fasta": {}},
            },
            {
                "id": "cm",
                "type": "codon_metrics",
                "outputs": {"metrics": {}, "metrics_table": {}, "per_record": {}, "per_record_json": {}},
            },
            {
                "id": "pred",
                "type": "simple_predictor_score",
                "params": {"model": ""},
                "outputs": {"predictions": {}, "predictions_json": {}},
            },
            {"id": "scorer", "type": "multi_objective_scorer", "outputs": {"ranked": {}, "table": {}}},
            {
                "id": "opt",
                "type": "group_relative_optimizer",
                "outputs": {"policy_table": {}, "elites": {}, "best": {}},
            },
        ],
        "edges": [
            {"source_node": "gen", "target_node": "cm", "source_output": "fasta", "target_input": "cds"},
            {
                "source_node": "cm",
                "target_node": "pred",
                "source_output": "per_record",
                "target_input": "feature_table",
            },
            {
                "source_node": "gen",
                "target_node": "scorer",
                "source_output": "candidates",
                "target_input": "candidates",
            },
            {
                "source_node": "pred",
                "target_node": "scorer",
                "source_output": "predictions",
                "target_input": "scores_1",
            },
            {
                "source_node": "gen",
                "target_node": "opt",
                "source_output": "candidates",
                "target_input": "candidates",
            },
            {"source_node": "scorer", "target_node": "opt", "source_output": "ranked", "target_input": "ranked"},
        ],
    }
    subgraph = {
        "id": "body",
        "type": "subgraph",
        "params": {
            "workflow": inner,
            "input_ports": [
                {"name": "in__gen__id_prefix", "type": "ANY", "innerNodeId": "gen", "innerSlot": "id_prefix"}
            ],
            "output_ports": [
                {
                    "name": "out__opt__policy_table",
                    "type": "ANY",
                    "innerNodeId": "opt",
                    "innerSlot": "policy_table",
                }
            ],
        },
        "outputs": {"out__opt__policy_table": {}},
    }
    return {
        "nodes": [
            {
                "id": "seed_path",
                "type": "string_format",
                "params": {"template": str(marker)},
                "outputs": {"text": {}},
            },
            {
                "id": "wl",
                "type": "while_loop",
                "params": {"condition_mode": "file_exists", "max_iterations": 2},
                "outputs": {"iteration": {}, "results": {}, "iterations": {}, "converged": {}},
            },
            subgraph,
        ],
        "edges": [
            {"source_node": "seed_path", "target_node": "wl", "source_output": "text", "target_input": "value"},
            {
                "source_node": "wl",
                "target_node": "body",
                "source_output": "iteration",
                "target_input": "in__gen__id_prefix",
            },
            {
                "source_node": "body",
                "target_node": "wl",
                "source_output": "out__opt__policy_table",
                "target_input": "value",
            },
        ],
    }


@pytest.mark.asyncio
async def test_while_loop_with_empty_evaluator_tables_completes(tmp_path: Path) -> None:
    marker = tmp_path / "marker.tsv"
    marker.write_text("id\tv\na\t1\n", encoding="utf-8")
    workflow = _empty_evaluator_loop_workflow(marker)
    assert validate_workflow(workflow, _registry()).valid is True, validate_workflow(workflow, _registry()).errors

    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=_registry())
    result = await executor.execute("empty-loop", workflow, force=True, emit=lambda *_: None)

    assert result["status"] == "completed", result.get("node_results")
    wl_outputs = result["node_results"]["wl"]["outputs"]
    assert wl_outputs["iterations"] == 2

    # Every iteration's evaluator produced a header-only per-record table; the
    # scorer ranked nothing; the optimizer emitted the zero-elite pass-through.
    run_root = tmp_path / "runs" / "empty-loop"
    for iteration_dir in sorted((run_root / "wl" / "iterations").iterdir()):
        predictions = list(iteration_dir.rglob("predictions.tsv"))
        assert predictions, iteration_dir
        assert dt_read_table(predictions[0], "\t")[1] == []
        elites_files = list(iteration_dir.rglob("elites.json"))
        assert elites_files, iteration_dir
        stats = json.loads(elites_files[0].read_text(encoding="utf-8"))["stats"]
        assert stats["n_candidates"] == 0 and stats["best_composite"] is None
