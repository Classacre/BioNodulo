from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load_template(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "templates" / name).read_text(encoding="utf-8"))


def _node_types(workflow: dict[str, Any]) -> dict[str, str]:
    return {str(node["id"]): str(node["type"]) for node in workflow["nodes"]}


def _node_by_id(workflow: dict[str, Any], node_id: str) -> dict[str, Any]:
    return next(node for node in workflow["nodes"] if node["id"] == node_id)


def _has_edge(workflow: dict[str, Any], source: str, source_output: str, target: str, target_input: str) -> bool:
    return any(
        edge.get("from") == {"node": source, "output": source_output}
        and edge.get("to") == {"node": target, "input": target_input}
        for edge in workflow["edges"]
    )


def test_metagenomics_template_retries_fragile_kraken2_and_humann_nodes_only() -> None:
    workflow = _load_template("metagenomics_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["kraken2_retry_001"] == "retry"
    assert node_types["humann_retry_001"] == "retry"
    assert node_types["humann_reads_001"] == "input_file"
    assert node_types["kraken2_001"] == "kraken2"
    assert node_types["humann_001"] == "humann"
    assert node_types["metaphlan_001"] == "metaphlan"

    kraken2_retry = _node_by_id(workflow, "kraken2_retry_001")
    assert kraken2_retry["params"]["max_retries"] == 2
    assert kraken2_retry["params"]["delay_seconds"] == 10.0
    assert kraken2_retry["params"]["backoff_multiplier"] == 2.0
    assert kraken2_retry["params"]["max_delay"] == 120
    assert kraken2_retry["params"]["retry_on"] == "all"
    assert kraken2_retry["params"]["only_retry_specific_nodes"] == "kraken2_001"

    humann_retry = _node_by_id(workflow, "humann_retry_001")
    assert humann_retry["params"]["max_retries"] == 2
    assert humann_retry["params"]["delay_seconds"] == 10.0
    assert humann_retry["params"]["backoff_multiplier"] == 2.0
    assert humann_retry["params"]["max_delay"] == 120
    assert humann_retry["params"]["retry_on"] == "all"
    assert humann_retry["params"]["only_retry_specific_nodes"] == "humann_001"

    assert _has_edge(workflow, "gate_trimmed_reads_001", "output", "kraken2_retry_001", "input")
    assert _has_edge(workflow, "kraken2_retry_001", "passthrough", "kraken2_001", "reads")
    assert _has_edge(workflow, "humann_reads_001", "file", "humann_retry_001", "input")
    assert _has_edge(workflow, "humann_retry_001", "passthrough", "humann_001", "input")
    assert _has_edge(workflow, "gate_trimmed_reads_001", "output", "metaphlan_001", "reads")

    assert not _has_edge(workflow, "gate_trimmed_reads_001", "output", "kraken2_001", "reads")
    assert not _has_edge(workflow, "gate_trimmed_reads_001", "output", "humann_001", "reads")
    assert not _has_edge(workflow, "gate_trimmed_reads_001", "output", "humann_retry_001", "input")
    assert not _has_edge(workflow, "gate_trimmed_reads_001", "output", "metaphlan_retry_001", "input")

    assert workflow["outputs"]["kraken2_retry_policy"] == "kraken2_retry_001"
    assert workflow["outputs"]["humann_retry_policy"] == "humann_retry_001"
