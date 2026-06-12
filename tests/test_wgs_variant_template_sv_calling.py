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


def test_wgs_variant_template_adds_parallel_manta_and_delly_sv_calling() -> None:
    workflow = _load_template("wgs_variant_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["manta_sv_001"] == "manta_call"
    assert node_types["delly_sv_001"] == "delly_call"
    assert node_types["sv_report_001"] == "html_report"

    manta = _node_by_id(workflow, "manta_sv_001")
    delly = _node_by_id(workflow, "delly_sv_001")
    report = _node_by_id(workflow, "sv_report_001")
    assert manta["params"]["threads"] == 4
    assert manta["params"]["exome"] is False
    assert manta["params"]["rna"] is False
    assert delly["params"]["mode"] == "call"
    assert delly["params"]["map_qual"] == 1
    assert "structural variants" in report["params"]["text_sections"]

    assert _has_edge(workflow, "markdup_001", "marked_bam", "manta_sv_001", "bam")
    assert _has_edge(workflow, "ref_001", "reference", "manta_sv_001", "reference")
    assert _has_edge(workflow, "markdup_001", "marked_bam", "delly_sv_001", "bam")
    assert _has_edge(workflow, "ref_001", "reference", "delly_sv_001", "reference")
    assert _has_edge(workflow, "manta_sv_001", "sv_vcf", "sv_report_001", "tables")
    assert _has_edge(workflow, "delly_sv_001", "sv_vcf", "sv_report_001", "tables")
    assert workflow["outputs"]["manta_sv"] == "manta_sv_001"
    assert workflow["outputs"]["delly_sv"] == "delly_sv_001"
    assert workflow["outputs"]["structural_variant_report"] == "sv_report_001"
