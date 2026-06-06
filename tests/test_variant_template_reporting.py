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


def test_variant_template_previews_final_variant_report() -> None:
    workflow = _load_template("variant_calling_pipeline.json")
    node_types = _node_types(workflow)

    assert node_types["vep_001"] == "vep"
    assert node_types["variant_report_001"] == "html_report"
    assert node_types["variant_report_preview_001"] == "html_preview"

    report = _node_by_id(workflow, "variant_report_001")
    assert report["params"]["section_names"] == (
        "VCF statistics,Coverage plot,SnpEff prioritized variants,VEP annotated variants"
    )

    assert _has_edge(workflow, "filter_001", "filtered_vcf", "vep_001", "vcf")
    assert _has_edge(workflow, "vcf_stats_001", "stats_image", "variant_report_001", "images")
    assert _has_edge(workflow, "coverage_plot_001", "coverage_image", "variant_report_001", "images")
    assert _has_edge(workflow, "gate_prioritized_vcf_001", "output", "variant_report_001", "tables")
    assert _has_edge(workflow, "vep_001", "annotated_vcf", "variant_report_001", "tables")
    assert _has_edge(workflow, "variant_report_001", "html_report", "variant_report_preview_001", "file")
    assert workflow["outputs"]["vep_annotation"] == "vep_001"
    assert workflow["outputs"]["variant_report_preview"] == "variant_report_preview_001"
