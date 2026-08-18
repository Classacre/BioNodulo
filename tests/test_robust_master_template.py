"""Master ROBUST Designer template: structure, planning, and a miniature execution.

The master template (templates/robust_designer.json) is the single-file campaign
deliverable: accession gate -> campaign config -> E1 design loop -> E2 baselines +
ablations + paired stats -> E3 learned evaluator -> E1-augmented rerun -> E4 m6A
validation (parallel GPU branch) -> master export. These tests keep it honest:

1. recursive validation against the real registry;
2. dry-run planning aggregates GPU + external executables and per-phase inner
   node counts;
3. every "Shared Evaluator" subgraph instance is deep-equal, and no subgraph
   embeds copy-pasted constants (weights, CDS literals, the retired hardcoded
   scores_1 prior);
4. a CI-sized miniature execution (one pair, two iterations, batch four, heavy
   phases muted) that exercises gate -> config -> E1 loop -> export with the
   live ensemble reward, fail-soft ViennaRNA/learned arms included.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest

from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.workflow.validation import validate_workflow

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
TEMPLATE_PATH = TEMPLATES / "robust_designer.json"

# The 720-nt codon-diverse GFP-derived demo ORF, kept ONLY as the miniature-run
# target so CI never touches the six real campaign FASTAs.
GFP_DEMO_ORF = (
    "ATGGCATCTAAAGGCGAAGAATTGTTTACCGGCGTGGTGCCTATACTAGTGGAGCTTGATGGAGATGTTAATGGTCATAAATTTTCAGTCTCTGGTGAAGGTGAAGGGGATGCGACGTATGGAAAGCTAACACTGAAATTTATCTGCACAACGGGCAAATTGCCAGTGCCATGGCCCACGCTGGTGACAACTTTTAGTTATGGGGTGCAATGTTTCAGCCGATACCCCGACCATATGAAGCAGCACGACTTCTTTAAATCAGCGATGCCCGAAGGGTATGTGCAAGAGCGTACAATCTTTTTCAAGGACGACGGTAACTATAAAACACGCGCTGAGGTTAAGTTCGAGGGAGATACTCTGGTGAATAGAATTGAACTGAAAGGAATCGACTTCAAGGAGGATGGCAACATTTTGGGCCACAAGCTAGAATATAATTATAATAGCCACAACGTCTACATCATGGCAGATAAGCAGAAAAATGGGATTAAAGTAAACTTCAAAATCAGACACAACATCGAGGACGGTTCTGTTCAATTGGCAGACCACTACCAACAGAATACGCCGATTGGCGACGGCCCCGTTTTGTTACCTGACAACCATTACTTATCAACACAATCGGCACTGAGCAAGGACCCTAACGAAAAACGTGACCATATGGTCTTACTGGAGTTTGTCACGGCCGCGGGTATAACGCATGGTATGGATGAACTCTATAAAGGT"
)

HEAVY_PHASES = {"e2", "e3", "e4", "e1_aug"}


def _load_template() -> dict[str, Any]:
    return json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))


def _registry() -> NodeRegistry:
    registry = NodeRegistry()
    registry.load_builtin_nodes()
    return registry


def _iter_nodes(workflow: dict[str, Any]):
    """Yield (workflow_owner_path, node) for every node incl. nested subgraphs."""
    for node in workflow.get("nodes", []):
        yield workflow, node
        if node.get("type") == "subgraph":
            yield from _iter_nodes(node["params"]["workflow"])


def _phase_subgraphs(workflow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        node["id"]: node
        for node in workflow["nodes"]
        if node.get("type") == "subgraph"
    }


def _evaluator_instances(workflow: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    found: list[tuple[str, dict[str, Any]]] = []
    for _, node in _iter_nodes(workflow):
        if node.get("type") == "subgraph" and (node.get("ui") or {}).get("title") == "Shared Evaluator":
            found.append((node["id"], node["params"]["workflow"]))
    return found


# ---------------------------------------------------------------------------
# structure + validation
# ---------------------------------------------------------------------------


def test_master_template_validates_recursively_against_the_registry() -> None:
    result = validate_workflow(_load_template(), _registry())

    assert result.valid is True, result.errors
    # Every phase subgraph contributes its inner nodes to the sorted order.
    order = result.sorted_node_order
    for prefix in ("e1/", "e2/", "e3/", "e4/", "e1_aug/"):
        assert any(node_id.startswith(prefix) for node_id in order), prefix


def test_master_template_layout_groups_and_ports() -> None:
    workflow = _load_template()

    group_names = [group["name"] for group in workflow["groups"]]
    assert len(workflow["groups"]) == 7
    assert group_names[0].startswith("0 · Accession Gate")
    assert group_names[-1].startswith("6 · Export")

    phases = _phase_subgraphs(workflow)
    assert set(phases) == {"e1", "e2", "e3", "e1_aug", "e4"}
    expected_inputs = {
        "e1": {"in__e1_prov__input_0", "in__fe_pairs__items"},
        "e2": {
            "in__e2_prov__input_0",
            "in__fe_b1__items",
            "in__fe_b2__items",
            "in__fe_b3__items",
            "in__fe_abl__items",
        },
        "e3": {"in__e3_prov__input_0", "in__const_filter__table", "in__ov_prep__json_path"},
        "e1_aug": {"in__cfg_aug__annotate_value"},
        "e4": {"in__e4_prov__input_0"},
    }
    for phase, ports in expected_inputs.items():
        declared = {p["name"] for p in phases[phase]["params"]["input_ports"]}
        assert declared == ports, (phase, declared)

    # The gate routes: all_pass -> if_condition -> phases / halt note.
    edge_map = {
        (e["from"]["node"], e["from"]["output"], e["to"]["node"]): e["to"]["input"]
        for e in workflow["edges"]
    }
    assert edge_map[("gate", "all_pass", "e1")] == "in__e1_prov__input_0"
    assert edge_map[("gate", "all_pass", "e4")] == "in__e4_prov__input_0"
    # The false branch documents the halt inline (note nodes are visual-only;
    # the executor filters them, so no edge may point at one).
    assert not [e for e in workflow["edges"] if e["to"]["node"] == "gate_halt"]
    halt_note = next(n for n in workflow["nodes"] if n["id"] == "gate_halt")
    assert "HALTED: accession verification failed" in halt_note["params"]["text"]
    # Phase ordering: e1 -> e2 -> e3 -> e1_aug (learned model), e4 parallel, export last.
    assert ("e3", "out__train__model", "e1_aug") in edge_map
    assert ("e1_aug", "subgraph_dir", "x") in edge_map
    assert ("e4", "subgraph_dir", "x") in edge_map

    node_ids = {node["id"] for node in workflow["nodes"]}
    for prefix in ("gate_", "cfg", "e1", "e2", "e3", "e4", "x", "note_"):
        assert any(node_id == prefix or node_id.startswith(prefix) for node_id in node_ids), prefix


def test_every_declared_tool_is_used_somewhere_in_the_master() -> None:
    workflow = _load_template()
    used = {node["type"] for _, node in _iter_nodes(workflow)}
    assert "note" in used
    assert used <= set(workflow["tools"]), sorted(used - set(workflow["tools"]))
    # The retired demo-prior and NIM/LLM arms from the previous 50-node graph are gone.
    assert "nim_test" not in used
    assert "llm_prompt" not in used
    assert "rnafold_partition" not in used


# ---------------------------------------------------------------------------
# shared-evaluator discipline + no constants inside subgraphs
# ---------------------------------------------------------------------------


def test_all_shared_evaluator_instances_are_deep_equal() -> None:
    workflow = _load_template()
    instances = _evaluator_instances(workflow)

    assert {node_id for node_id, _ in instances} == {
        "d1_ev",  # E1 design loop
        "da_ev",  # E1-augmented rerun
        "b1_ev",  # B1 random baseline
        "b2_ev",  # B2 codon_optimizer baseline
        "b3_ev",  # B3 LinearDesign baseline
        "dv_ev",  # ablation mini-campaigns
        "ev_e3",  # E3 construct panel
    }
    first = json.dumps(instances[0][1], sort_keys=True)
    for node_id, inner in instances[1:]:
        assert json.dumps(inner, sort_keys=True) == first, node_id

    # The learned member's model port is DECLARED everywhere but only wired in
    # the augmented rerun (parent-level edge e3.out__train__model -> e1_aug).
    workflow_edges = _load_template()["edges"]
    assert all(
        e["from"]["node"] == "e3" and e["to"]["node"] == "e1_aug"
        for e in workflow_edges
        if e["to"]["input"] == "in__cfg_aug__annotate_value"
    )


def test_no_copy_pasted_constants_inside_any_subgraph() -> None:
    workflow = _load_template()
    codon_literal = re.compile(r"^[ACGT]{90,}$")

    for owner, node in _iter_nodes(workflow):
        if owner is workflow:
            continue  # top-level nodes may carry file paths / tables
        params = node.get("params", {})
        for key, value in params.items():
            if key == "weights":
                assert value in ("", "{}"), (node["id"], value)
            if isinstance(value, str) and codon_literal.match(value.strip()):
                pytest.fail(f"subgraph node {node['id']} embeds a CDS literal in '{key}'")
            if key == "scores_1" and "cand_" in str(value):
                pytest.fail(f"scorer {node['id']} still carries the retired static prior")

    # The retired hardcoded per-candidate prior (cand_0000..cand_0023) is gone
    # from the entire template; scores_1 is now a wired ensemble port.
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert not re.search(r'\{"id": ?"cand_\d+", ?"score"', text)
    assert not re.search(r'cand_00\d\d', text)


def test_weights_reach_scorers_through_ports_not_params() -> None:
    workflow = _load_template()

    for _, node in _iter_nodes(workflow):
        if node.get("type") != "multi_objective_scorer":
            continue
        # No static weights param: the port-keyed weights_json row feeds the edge.
        assert node.get("params", {}).get("weights", "") == ""
    # Every scorer receives weights via an incoming edge.
    edge_targets = {(e["to"]["node"], e["to"]["input"]) for e in _all_edges(workflow)}
    for _, node in _iter_nodes(workflow):
        if node.get("type") == "multi_objective_scorer":
            assert (node["id"], "weights") in edge_targets, node["id"]


def _all_edges(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    edges = list(workflow.get("edges", []))
    for _, node in _iter_nodes(workflow):
        if node.get("type") == "subgraph":
            edges.extend(node["params"]["workflow"].get("edges", []))
    return edges


# ---------------------------------------------------------------------------
# dry-run planning
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dry_run_plans_all_phases_and_aggregates_requirements(tmp_path: Path) -> None:
    executor = WorkflowExecutor(
        workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=_registry()
    )

    preview = await executor.dry_run("plan-robust-master", _load_template())

    assert preview["status"] == "dry_run", preview.get("error")
    entries = {entry["node_id"]: entry for entry in preview["nodes"]}
    for phase in ("e1", "e2", "e3", "e4", "e1_aug"):
        assert entries[phase].get("inner_node_count", 0) > 0, phase
    assert preview["requirements"]["gpu"] is True
    assert "e4/dorado" in preview["requirements"]["gpu_nodes"]
    for executable in ("dorado", "samtools", "modkit", "aws", "RNAfold"):
        assert executable in preview["requirements"]["executables"]
    assert not [entry for entry in preview["nodes"] if "inner_error" in entry]


# ---------------------------------------------------------------------------
# accession gate over the real repo manifest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repo_verified_inputs_manifest_passes_the_gate(tmp_path: Path) -> None:
    from bionodulo.nodes.builtin.ml_design_family import AccessionGateNode

    repo_root = TEMPLATES.parent
    manifest = TEMPLATES / "data" / "verified_inputs_manifest.tsv"
    node = AccessionGateNode()
    status_path, all_pass = await node.run(
        manifest=str(manifest),
        require_files_exist=True,
        fail_closed=False,
        context=type("Ctx", (), {"node_dir": tmp_path})(),
    )
    payload = json.loads(Path(status_path).read_text(encoding="utf-8"))
    assert all_pass is True, [row["errors"] for row in payload["rows"] if row["errors"]]
    assert payload["n_rows"] == 16
    assert all(row["file_status"] == "verified" for row in payload["rows"])
    # Repo-relative data/ entries resolve from the repo root cwd.
    assert (repo_root / "data" / "egfp_u55762.fasta").is_file()


# ---------------------------------------------------------------------------
# miniature end-to-end execution (CI-sized; pure-Python path)
# ---------------------------------------------------------------------------


def _miniature(workflow: dict[str, Any], smoke_fasta: Path) -> dict[str, Any]:
    """One pair, two iterations, batch four; heavy phases muted; export kept live."""
    miniature = copy.deepcopy(workflow)
    for node in miniature["nodes"]:
        if node["id"] == "cfg":
            node["params"]["targets"] = f"egfp_smoke\t{smoke_fasta}"
            node["params"]["seeds"] = "13"
            node["params"]["iterations"] = 2
            node["params"]["batch_size"] = 4
            node["params"]["ablation_weights"] = ""
        if node["id"] in HEAVY_PHASES:
            node.setdefault("meta", {})["muted"] = True

    for _, node in _iter_nodes(miniature):
        if node.get("type") == "while_loop":
            node["params"]["max_iterations"] = 2
        if node.get("type") in {"policy_sampler", "candidate_generator"}:
            node["params"]["n_candidates"] = 4

    miniature["edges"] = [
        edge
        for edge in miniature["edges"]
        if not (edge["to"]["node"] == "x" and edge["from"]["node"] in HEAVY_PHASES)
    ]
    return miniature


@pytest.mark.asyncio
async def test_miniature_master_run_completes_with_live_ensemble_reward(tmp_path: Path) -> None:
    smoke_fasta = tmp_path / "egfp_smoke.fasta"
    smoke_fasta.write_text(">egfp_smoke demo ORF (miniature CI target only)\n" + GFP_DEMO_ORF + "\n", encoding="utf-8")
    workflow = _miniature(_load_template(), smoke_fasta)

    executor = WorkflowExecutor(
        workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=_registry()
    )
    result = await executor.execute(
        "mini-master", workflow, force=True, options={"embed_provenance": False}
    )

    assert result["status"] == "completed", _failures(result)

    # Gate verified the staged repo inputs and routed the true branch.
    assert result["node_results"]["gate"]["outputs"]["all_pass"] is True
    assert result["node_results"]["gate"]["outputs"]["all_pass"] is True
    for phase in HEAVY_PHASES:
        assert result["node_results"][phase]["status"] == "muted"

    # E1 loop artifacts: one pair, exactly two while iterations, optimizer elites present.
    e1_root = tmp_path / "runs" / "mini-master" / "e1"
    while_iterations = sorted(e1_root.glob("fe_pairs/iterations/*/d1_wl/iterations/*"))
    assert [path.name for path in while_iterations] == ["0001", "0002"]
    composites: list[float] = []
    for iteration_dir in while_iterations:
        elites_files = list(iteration_dir.rglob("elites.json"))
        assert elites_files, iteration_dir
        stats = json.loads(elites_files[0].read_text(encoding="utf-8"))["stats"]
        composites.append(float(stats["best_composite"]))
    # The ensemble-driven reward MOVES: at least two distinct best_composite values.
    assert len(set(composites)) >= 2, composites

    # No static prior: the executed scorer's scores_1 came from the evaluator
    # port (ranked.json per_objective carries live evaluator columns).
    ranked_files = sorted(e1_root.glob("fe_pairs/iterations/*/d1_wl/iterations/*/d1_scorer/**/*.json"))
    assert ranked_files
    per_iteration_objectives = []
    for ranked in ranked_files:
        payload = json.loads(ranked.read_text(encoding="utf-8"))
        if not isinstance(payload, list) or not payload:
            continue
        per_iteration_objectives.append(set(payload[0].get("per_objective", {})))
    live_objectives = set().union(*per_iteration_objectives)
    assert "scores_1" in live_objectives  # codon CAI (live per-record table)
    assert "scores_4" in live_objectives  # immune burden
    assert "scores_5" in live_objectives  # miRNA hits
    # Fold/learned arms degrade fail-soft on CI (no ViennaRNA / no model) and are
    # simply absent rather than fatal.
    assert "scores_6" not in live_objectives

    # Master export scanned the run tree and produced per-subgraph rows.
    export = result["node_results"]["x"]
    assert export["status"] == "completed"
    per_subgraph = Path(export["outputs"]["per_subgraph"]).read_text(encoding="utf-8").splitlines()
    header = per_subgraph[0].split("\t")
    rows = [dict(zip(header, line.split("\t"), strict=True)) for line in per_subgraph[1:]]
    while_rows = [row for row in rows if row["subgraph"].endswith("/d1_wl")]
    assert len(while_rows) == 1
    assert while_rows[0]["n_iterations"] == "2"
    assert while_rows[0]["best_id"].startswith("cand_")
    assert float(while_rows[0]["best_scores_1"]) > 0.0  # live CAI of the best design


def _failures(result: dict[str, Any]) -> str:
    return "\n".join(
        f"{node_id}: {str(node.get('error'))[:300]}"
        for node_id, node in result.get("node_results", {}).items()
        if isinstance(node, dict) and node.get("status") == "failed"
    )
