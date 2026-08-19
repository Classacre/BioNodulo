"""Engine-level checks for the master ROBUST Designer template.

This file deliberately asserts only what the ENGINE guarantees for any
workflow of this shape — recursive structural validity against the real
registry, subgraph-instance discipline, and "a 2-iteration miniature does not
crash on empty candidate batches". Authoring choices of this one template
(layout, ports, tool lists, weights wiring, specific numbers) are not engine
contracts and are not tested here.
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

# Failures the empty-tolerance engine work explicitly permits: a muted or
# degenerate phase may report an empty/missing input, but nothing may crash
# with an unexpected error class.
KNOWN_EMPTY_TOLERANCE = (
    re.compile(pattern)
    for pattern in (
        r"no data rows",
        r"zero data rows",
        r"does not exist",
        r"not an existing file",
        r"Source not found",
        r"must be a non-empty",
        r"is empty",
        r"contains no data",
    )
)


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


def _evaluator_instances(workflow: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    found: list[tuple[str, dict[str, Any]]] = []
    for _, node in _iter_nodes(workflow):
        if node.get("type") == "subgraph" and (node.get("ui") or {}).get("title") == "Shared Evaluator":
            found.append((node["id"], node["params"]["workflow"]))
    return found


def _failures(result: dict[str, Any]) -> str:
    return "\n".join(
        f"{node_id}: {str(node.get('error'))[:300]}"
        for node_id, node in result.get("node_results", {}).items()
        if isinstance(node, dict) and node.get("status") == "failed"
    )


def test_master_template_validates_against_the_registry() -> None:
    result = validate_workflow(_load_template(), _registry())
    assert result.valid is True, result.errors


def test_all_shared_evaluator_instances_are_deep_equal() -> None:
    instances = _evaluator_instances(_load_template())
    assert len(instances) >= 2, "expected multiple Shared Evaluator instances"

    first = json.dumps(instances[0][1], sort_keys=True)
    for node_id, inner in instances[1:]:
        assert json.dumps(inner, sort_keys=True) == first, node_id


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
async def test_miniature_master_run_does_not_crash_on_empty_batches(tmp_path: Path) -> None:
    """The engine must survive this graph shape: loops + subgraphs + evaluators
    + joins + scorers across a 2-iteration run with empty-capable batches.

    The contract is "completed, or failed only with known empty-tolerance
    errors" — never a crash on an empty candidate batch.
    """
    smoke_fasta = tmp_path / "egfp_smoke.fasta"
    smoke_fasta.write_text(
        ">egfp_smoke demo ORF (miniature CI target only)\n" + GFP_DEMO_ORF + "\n", encoding="utf-8"
    )

    executor = WorkflowExecutor(
        workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=_registry()
    )
    result = await executor.execute(
        "mini-master", _miniature(_load_template(), smoke_fasta), force=True,
        options={"embed_provenance": False},
    )

    if result["status"] != "completed":
        failed = {
            node_id: node
            for node_id, node in result.get("node_results", {}).items()
            if isinstance(node, dict) and node.get("status") == "failed"
        }
        assert failed, _failures(result)
        for node_id, node in failed.items():
            error = str(node.get("error", ""))
            assert any(pattern.search(error) for pattern in KNOWN_EMPTY_TOLERANCE), (
                f"{node_id} failed outside known empty-tolerance patterns: {error[:300]}"
            )
