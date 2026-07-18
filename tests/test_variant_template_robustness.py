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


def test_variant_template_retries_gatk_haplotype_caller() -> None:
    workflow = _load_template("variant_calling_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["gatk_retry_001"] == "retry"
    assert node_types["gatk_001"] == "gatk_haplotype_caller"
    assert node_types["index_001"] == "samtools_index"

    retry = _node_by_id(workflow, "gatk_retry_001")
    assert retry["params"]["max_retries"] == 2
    assert retry["params"]["delay_seconds"] == 10.0
    assert retry["params"]["backoff_multiplier"] == 2.0
    assert retry["params"]["retry_on"] == "all"
    assert retry["params"]["only_retry_specific_nodes"] == "gatk_001"

    assert _has_edge(workflow, "markdup_001", "marked_bam", "index_001", "bam")
    assert _has_edge(workflow, "index_001", "indexed_bam", "gatk_retry_001", "input")
    assert _has_edge(workflow, "gatk_retry_001", "passthrough", "gatk_001", "bam")
    assert _has_edge(workflow, "index_001", "bai", "gatk_001", "bam_index")
    assert _has_edge(workflow, "ref_sidecars_001", "reference", "gatk_001", "reference")
    assert _has_edge(workflow, "ref_sidecars_001", "fai_index", "gatk_001", "reference_index")
    assert _has_edge(
        workflow,
        "ref_sidecars_001",
        "sequence_dictionary",
        "gatk_001",
        "sequence_dictionary",
    )
    assert not _has_edge(workflow, "markdup_001", "marked_bam", "gatk_retry_001", "input")
    assert not _has_edge(workflow, "markdup_001", "marked_bam", "gatk_001", "bam")
    assert workflow["outputs"]["gatk_retry_policy"] == "gatk_retry_001"
