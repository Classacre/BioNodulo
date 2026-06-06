from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load_template(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "templates" / name).read_text(encoding="utf-8"))


def _node_types(workflow: dict[str, Any]) -> dict[str, str]:
    return {str(node["id"]): str(node["type"]) for node in workflow["nodes"]}


def _has_edge(workflow: dict[str, Any], source: str, source_output: str, target: str, target_input: str) -> bool:
    return any(
        edge.get("from") == {"node": source, "output": source_output}
        and edge.get("to") == {"node": target, "input": target_input}
        for edge in workflow["edges"]
    )


def test_single_cell_template_retries_only_cellranger_count_after_fastq_validation() -> None:
    workflow = _load_template("single_cell_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["cr_count_retry_001"] == "retry"
    retry = next(node for node in workflow["nodes"] if node["id"] == "cr_count_retry_001")
    assert retry["params"] == {
        "max_retries": 2,
        "delay_seconds": 5.0,
        "backoff_multiplier": 2.0,
        "max_delay": 120,
        "retry_on": "all",
        "only_retry_specific_nodes": "cr_count_001",
    }

    assert _has_edge(workflow, "fastq_001", "directory", "validate_fastq_dir_001", "input")
    assert _has_edge(workflow, "validate_fastq_dir_001", "passthrough", "cr_count_retry_001", "input")
    assert _has_edge(workflow, "cr_count_retry_001", "passthrough", "cr_count_001", "fastq_dir")
    assert _has_edge(workflow, "validate_reference_dir_001", "passthrough", "cr_count_001", "transcriptome")
    assert not _has_edge(workflow, "validate_fastq_dir_001", "passthrough", "cr_count_001", "fastq_dir")
    assert not _has_edge(workflow, "fastq_001", "directory", "cr_count_001", "fastq_dir")
    assert not _has_edge(workflow, "ref_001", "directory", "cr_count_001", "transcriptome")
    assert workflow["outputs"]["cellranger_retry_policy"] == "cr_count_retry_001"
