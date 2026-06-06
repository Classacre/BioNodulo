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


def test_assembly_template_retries_spades_branch_after_assembler_switch() -> None:
    workflow = _load_template("assembly_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["switch_assembler_001"] == "switch"
    assert node_types["spades_retry_001"] == "retry"
    assert node_types["spades_001"] == "spades"

    retry = _node_by_id(workflow, "spades_retry_001")
    assert retry["params"]["max_retries"] == 2
    assert retry["params"]["delay_seconds"] == 5.0
    assert retry["params"]["backoff_multiplier"] == 2.0
    assert retry["params"]["retry_on"] == "all"
    assert retry["params"]["only_retry_specific_nodes"] == "spades_001"

    assert _has_edge(workflow, "switch_assembler_001", "output_1", "spades_retry_001", "input")
    assert _has_edge(workflow, "spades_retry_001", "passthrough", "spades_001", "reads")
    assert not _has_edge(workflow, "switch_assembler_001", "output_1", "spades_001", "reads")
    assert workflow["outputs"]["spades_retry_policy"] == "spades_retry_001"
